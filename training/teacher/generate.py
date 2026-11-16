"""Teacher trajectory generator (plan T13): run a teacher policy through the real agent loop on TRAIN tasks and keep
only the trajectories that pass the checker against the gold spec (ARCH §7.3, RULES §5).

The teacher sees exactly what the student will see (system prompt v1 + request + probes): never the gold spec or
the reference command. Resumable (finished task ids are skipped), budget-guarded by the policy's BudgetGuard,
and it refuses to run on a draft prompt or on any split but train.
"""

import dataclasses
import hashlib
import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from pathlib import Path

from training import config
from training.env.loop import Policy, initial_messages, run_episode, score
from training.env.probe import probe
from training.teacher.budget import BudgetExceeded, BudgetGuard


class PromptNotFrozen(RuntimeError):
    pass


class OffPeakRequired(RuntimeError):
    pass


@dataclass
class GenSummary:
    attempted: int = 0
    kept: int = 0
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


def make_record(
    task: dict, ep, corpus: dict[str, Path], prompt: str, passed: bool, cost_usd: float
) -> dict:
    """One trajectory record: the full conversation the model saw/produced, the verdict and the episode."""
    messages = initial_messages(task, {c: probe(corpus[c]) for c in task["inputs"]}, prompt)
    for turn in ep.turns:
        messages += [
            {"role": "assistant", "content": turn["assistant"]},
            {"role": "user", "content": json.dumps(turn["observation"])},
        ]
    return {
        "task_id": task["id"], "families": task["families"], "passed": passed, "runs": ep.runs,
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
) -> GenSummary:
    if any(t["split"] != "train" for t in tasks):
        raise PermissionError("teacher generation reads train tasks only (RULES §4.5)")
    prompt = load_prompt_v1(allow_draft_prompt)
    out_dir.mkdir(parents=True, exist_ok=True)
    traj, kept = out_dir / "trajectories.jsonl", out_dir / "kept.jsonl"
    done = _done_ids(traj)
    summary, fam_kept, fam_all = GenSummary(), Counter(), Counter()
    for task in tasks:
        if task["id"] in done:
            summary.skipped_done += 1
            continue
        if max_episodes is not None and summary.attempted >= max_episodes:
            break
        if offpeak_only and not is_offpeak(now()):
            raise OffPeakRequired(
                "bulk teacher runs are off-peak only (RULES §5.3); the peak windows are config.DEEPSEEK_PEAK_UTC"
            )
        before = guard.spent(run_only=True) if guard else 0.0
        try:
            ep = run_episode(
                task, policy, corpus=corpus, job_dir=out_dir / "jobs" / task["id"], system_prompt_text=prompt,
                require_spec=True, stop_after_ask=True,
            )  # fmt: skip
        except BudgetExceeded as e:
            summary.stopped = f"budget: {e}"
            break
        passed = score(task, ep)
        rec = make_record(
            task,
            ep,
            corpus,
            prompt,
            passed,
            (guard.spent(run_only=True) - before) if guard else 0.0,
        )
        with traj.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        if passed:
            with kept.open("a") as f:
                f.write(json.dumps(rec) + "\n")
        summary.attempted += 1
        summary.kept += passed
        key = "+".join(task["families"]) or "unsupported"
        fam_all[key] += 1
        fam_kept[key] += passed
    summary.cost_usd = guard.spent(run_only=True) if guard else 0.0
    summary.cache_hit_ratio = guard.cache_hit_ratio() if guard else 0.0
    summary.by_family = {k: f"{fam_kept[k]}/{fam_all[k]}" for k in sorted(fam_all)}
    return summary
