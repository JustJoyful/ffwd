"""Teacher trajectory generator (plan T13): run a teacher policy through the real agent loop on TRAIN tasks and keep
only the trajectories that pass the checker against the gold spec (ARCH §7.3, RULES §5).

The teacher sees exactly what the student will see (system prompt v1 + request + probes): never the gold spec or
the reference command. Resumable (finished task ids are skipped), budget-guarded by the policy's BudgetGuard,
and it refuses to run on a draft prompt or on any split but train.
"""

import dataclasses
import hashlib
import json
import shutil
import threading
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from training import config
from training.env.actions import ParseError, parse_action
from training.env.loop import Policy, initial_messages, run_episode, score
from training.env.probe import probe
from training.taskgen.special import nearest_ok
from training.teacher.budget import BudgetExceeded, BudgetGuard

PEAK_MARGIN = timedelta(minutes=5)  # no episode starts within this long of a peak window


class PromptNotFrozen(RuntimeError):
    pass


class OffPeakRequired(RuntimeError):
    pass


@dataclass
class GenSummary:
    attempted: int = 0
    passed: int = 0  # checker verdict only: the preregistered kept-rate gate is measured on this
    kept: int = 0  # passed AND label_ok: what goes to SFT
    label_rejected: int = 0
    errors: int = 0  # episodes that crashed (API/network): not recorded, retried by the next call
    last_error: str | None = None
    skipped_done: int = 0
    cost_usd: float = 0.0
    cache_hit_ratio: float = 0.0
    stopped: str | None = None
    by_family: dict = field(default_factory=dict)


def load_prompt_v1(allow_draft: bool = False) -> str:
    text = (config.PROTOCOL_DIR / "prompts" / config.SYSTEM_PROMPT_V1).read_text()
    if config.SYSTEM_PROMPT_V1_SHA256 is None:
        if not allow_draft:
            raise PromptNotFrozen(
                "system prompt v1 is a DRAFT (config.SYSTEM_PROMPT_V1_SHA256 is None); freeze it first"
            )
    elif hashlib.sha256(text.encode()).hexdigest() != config.SYSTEM_PROMPT_V1_SHA256:
        raise PromptNotFrozen("system prompt v1 no longer matches its pinned hash")
    return text


def is_offpeak(now: datetime, peak: tuple[tuple[time, time], ...] | None = None) -> bool:
    """Off-peak = not inside any (start, end) UTC peak window (config.DEEPSEEK_PEAK_UTC; end exclusive)."""
    t = now.astimezone(UTC).time()
    return not any(start <= t < end for start, end in (peak or config.DEEPSEEK_PEAK_UTC))


def teacher_nearest(ep) -> str | None:
    """The `nearest_supported` the teacher gave in its `unsupported` action (None if absent or not an unsupported run)."""
    for turn in ep.turns:
        a = parse_action(turn["assistant"])
        if not isinstance(a, ParseError) and a.get("action") == "unsupported":
            return a.get("nearest_supported")
    return None


def label_ok(task: dict, ep) -> bool:
    """Only unsupported tasks carry a checkable label: the teacher's `nearest_supported` must be one the generator
    accepts (special.NEAREST_ACCEPTED). `score()` does not look at it; the trajectory is filtered, never edited.
    """
    return not task["flags"]["unsupported"] or nearest_ok(task, teacher_nearest(ep))


def seconds_until_offpeak(now: datetime) -> int:
    """0 if a new episode may start now (incl. the margin), else seconds to the first minute that may."""
    for minutes in range(0, 3 * 24 * 60):
        if is_offpeak(now + timedelta(minutes=minutes) + PEAK_MARGIN):
            return minutes * 60
    raise RuntimeError("no off-peak minute within 3 days: config.DEEPSEEK_PEAK_UTC is wrong")


def make_record(
    task: dict, ep, corpus: dict[str, Path], prompt: str, passed: bool, cost_usd: float,
    label: bool = True,
) -> dict:  # fmt: skip
    """One trajectory record: the full conversation the model saw/produced, the verdict and the episode."""
    messages = initial_messages(task, {c: probe(corpus[c]) for c in task["inputs"]}, prompt)
    for turn in ep.turns:
        messages += [
            {"role": "assistant", "content": turn["assistant"]},
            {"role": "user", "content": json.dumps(turn["observation"])},
        ]
    return {
        "task_id": task["id"], "families": task["families"], "passed": passed, "label_ok": label, "runs": ep.runs,
        "end_reason": ep.end_reason, "invalid_turns": ep.invalid_turns, "cost_usd": round(cost_usd, 8),
        "messages": messages, "episode": dataclasses.asdict(ep),
    }  # fmt: skip


def _done_ids(path: Path) -> set[str]:
    return (
        {json.loads(x)["task_id"] for x in path.read_text().splitlines()}
        if path.exists()
        else set()
    )


def generate(
    tasks: list[dict],
    out_dir: Path,
    policy: Policy,
    guard: BudgetGuard | None,
    corpus: dict[str, Path],
    *,
    allow_draft_prompt: bool = False,
    offpeak_only: bool = False,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    max_episodes: int | None = None,
    keep_jobs: bool = False,
    workers: int = 1,
    stop_on_peak: bool = False,
) -> GenSummary:
    """Run up to `max_episodes` unfinished tasks on `workers` threads. Records are written by the calling thread only.
    `stop_on_peak`: instead of raising OffPeakRequired, stop cleanly (summary.stopped) so the caller can resume later.
    """
    if any(t["split"] != "train" for t in tasks):
        raise PermissionError("teacher generation reads train tasks only (RULES §4.5)")
    prompt = load_prompt_v1(allow_draft_prompt)
    out_dir.mkdir(parents=True, exist_ok=True)
    traj, kept = out_dir / "trajectories.jsonl", out_dir / "kept.jsonl"
    done = _done_ids(traj)
    summary, fam_kept, fam_all = GenSummary(), Counter(), Counter()
    pending = [t for t in tasks if t["id"] not in done]
    summary.skipped_done = len(tasks) - len(pending)
    pending = pending[:max_episodes] if max_episodes is not None else pending
    halt, reason = threading.Event(), []

    def work(task: dict):
        if halt.is_set():
            return None
        if offpeak_only and not is_offpeak(now() + PEAK_MARGIN):
            reason.append("peak window")
            halt.set()
            return None
        if guard:
            guard.thread_cost(reset=True)
        try:
            ep = run_episode(
                task, policy, corpus=corpus, job_dir=out_dir / "jobs" / task["id"], system_prompt_text=prompt,
                require_spec=True, stop_after_ask=True,
            )  # fmt: skip
            return task, make_record(
                task,
                ep,
                corpus,
                prompt,
                score(task, ep),
                guard.thread_cost() if guard else 0.0,
                label_ok(task, ep),
            )
        except BudgetExceeded as e:
            reason.append(f"budget: {e}")
            halt.set()
            return None
        except (
            Exception
        ) as e:  # noqa: BLE001  API/network failure: the task stays unfinished and is retried next call
            return task, e
        finally:
            if (
                not keep_jobs
            ):  # the record holds the whole transcript; outputs of thousands of tasks fill the disk
                shutil.rmtree(out_dir / "jobs" / task["id"], ignore_errors=True)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for res in pool.map(
            work, pending
        ):  # in task order, so a stop leaves no gaps in the done set's prefix
            if res is None:
                continue
            task, rec = res
            if isinstance(rec, Exception):
                summary.errors += 1
                summary.last_error = f"{type(rec).__name__}: {rec}"[:300]
                continue
            with traj.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            ok = rec["passed"] and rec["label_ok"]
            if ok:
                with kept.open("a") as f:
                    f.write(json.dumps(rec) + "\n")
            summary.attempted += 1
            summary.passed += rec["passed"]
            summary.kept += ok
            summary.label_rejected += rec["passed"] and not rec["label_ok"]
            key = "+".join(task["families"]) or "unsupported"
            fam_all[key] += 1
            fam_kept[key] += ok
    if reason:
        if reason[0] == "peak window" and not stop_on_peak:
            raise OffPeakRequired(
                "bulk teacher runs are off-peak only (RULES §5.3); the peak windows are config.DEEPSEEK_PEAK_UTC"
            )
        summary.stopped = reason[0]
    summary.cost_usd = guard.spent(run_only=True) if guard else 0.0
    summary.cache_hit_ratio = guard.cache_hit_ratio() if guard else 0.0
    summary.by_family = {k: f"{fam_kept[k]}/{fam_all[k]}" for k in sorted(fam_all)}
    return summary
