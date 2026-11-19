"""Run the teacher (DeepSeek V4 Flash) on TRAIN tasks: the pilot (plan T13) and, later, the bulk run (T14).

uv run python -m training.teacher.run pilot --budget-usd 0.05 --name <name>
uv run python -m training.teacher.run bulk  --budget-usd 2.30 --name <name> [--limit N]

Both go through BudgetGuard (reserve before, settle after, hard caps) with the frozen prompt v1, thinking off, the
agent loop options the student will face (spec first, stop after one clarification). Work files go to
data/teacher/<name> (gitignored); the pilot copies its small artifacts into reports/. `pilot` and `bulk` refuse to
run inside a DeepSeek peak window (config.DEEPSEEK_PEAK_UTC); the pilot picks a fixed stratified set of tasks.
"""

import argparse
import dataclasses
import json
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from training import config
from training.policies import policy_from_config
from training.taskgen.clips import visible_records
from training.taskgen.loader import load_tasks
from training.teacher.budget import BudgetGuard
from training.teacher.datacard import build_card
from training.teacher.generate import generate, is_offpeak, refilter, seconds_until_offpeak
from training.teacher.oracle import OraclePolicy, select_oracle

MODEL_CONFIG = config.REPO_ROOT / "eval" / "configs" / "x1-deepseek-v1.toml"
PILOT_COMPOSITIONS = {
    2: 2,
    3: 2,
    4: 2,
}  # families -> how many composed tasks on top of one per family


def pilot_selection(tasks: list[dict]) -> list[dict]:
    """20 tasks: one single-family task per F1..F12 (incl. F11), one ambiguous, one unsupported, and composed tasks.
    Deterministic: the first match by task id (ids are content hashes, so this is arbitrary but fixed).
    """
    ordered = sorted(tasks, key=lambda t: t["id"])
    picked: list[dict] = []

    def first(pred) -> None:
        t = next((t for t in ordered if pred(t) and t not in picked), None)
        if t is not None:
            picked.append(t)

    plain = lambda t: not t["flags"]["ambiguous"] and not t["flags"]["unsupported"]  # noqa: E731
    for k in range(1, 13):
        first(lambda t, k=k: plain(t) and t["families"] == [f"F{k}"])
    first(lambda t: t["flags"]["ambiguous"])
    first(lambda t: t["flags"]["unsupported"])
    for n, how_many in PILOT_COMPOSITIONS.items():
        for _ in range(how_many):
            first(lambda t, n=n: plain(t) and len(t["families"]) == n)
    return picked


def _finished(work: Path) -> set[str]:
    f = work / "trajectories.jsonl"
    return {json.loads(x)["task_id"] for x in f.read_text().splitlines()} if f.exists() else set()


def corpus() -> dict[str, Path]:
    return {r["id"]: config.CORPUS_DIR / r["file"] for r in visible_records()}


def bulk(
    tasks, work, policy, guard, *, workers, chunk, gate, gate_min_n, sleep=time.sleep, now=None
) -> str:
    """Chunked bulk run. Returns why it ended: complete | budget | gate | errors. A peak window is not an end: the loop
    sleeps until the next off-peak minute and resumes (finished task ids are skipped, so it is also safe to restart).
    """
    now = now or (lambda: datetime.now(UTC))
    log, failures, n = work / "chunks.jsonl", 0, 0
    while True:
        if wait := seconds_until_offpeak(now()):
            print(f"[{now():%d %b %H:%M}Z] peak window: sleeping {wait // 60} min", flush=True)
            sleep(wait)
            continue
        before = guard.spent(run_only=True)
        s = generate(
            tasks, work, policy, guard, corpus(), offpeak_only=True, max_episodes=chunk, workers=workers,
            stop_on_peak=True,
        )  # fmt: skip
        n += 1
        rate = s.passed / s.attempted if s.attempted else float("nan")
        row = {
            "chunk": n, "at": now().isoformat(timespec="seconds"), "attempted": s.attempted, "passed": s.passed,
            "kept_rate": round(rate, 4), "kept": s.kept, "label_rejected": s.label_rejected, "errors": s.errors,
            "chunk_cost_usd": round(s.cost_usd - before, 6), "running_cost_usd": round(s.cost_usd, 6),
            "cache_hit": round(s.cache_hit_ratio, 4), "stopped": s.stopped, "remaining": len(tasks) - s.skipped_done - s.attempted,
            "by_family": s.by_family, "last_error": s.last_error,
        }  # fmt: skip
        with log.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(
            f"[chunk {n}] {s.attempted} run, kept-rate {rate:.1%} ({s.passed} passed, {s.kept} kept, "
            f"{s.label_rejected} label-rejected, {s.errors} errors), chunk ${row['chunk_cost_usd']:.4f}, "
            f"running ${s.cost_usd:.4f}, cache-hit {s.cache_hit_ratio:.1%}, remaining {row['remaining']}"
            + (f", stopped: {s.stopped}" if s.stopped else ""),
            flush=True,
        )
        if s.stopped and s.stopped.startswith("budget"):
            return "budget"
        if s.attempted >= gate_min_n and rate < gate:
            return "gate"
        failures = failures + 1 if s.errors and not s.attempted else 0
        if failures >= 5:
            return "errors"
        if s.errors and not s.attempted:
            sleep(60)
        elif not s.attempted and not s.stopped and not s.errors:
            return "complete"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["pilot", "bulk", "refilter", "oracle"])
    ap.add_argument("--name", required=True, help="unique run name (also the ledger run id)")
    ap.add_argument("--budget-usd", type=float, default=0.0)
    ap.add_argument(
        "--limit", type=int, default=None, help="bulk: stop after this many new episodes"
    )
    ap.add_argument(
        "--report-dir", type=Path, default=None, help="pilot: where to copy the small artifacts"
    )
    a = ap.parse_args()
    if (
        a.mode == "oracle"
    ):  # free: programmatic trajectories for what the teacher did not cover (D-032, <= 29% of the mix)
        work = config.DATA_DIR / "teacher" / a.name
        tasks = load_tasks("train", purpose="teacher")
        kept = [json.loads(x) for x in (work / "kept.jsonl").read_text().splitlines()]
        para = work / "paraphrases.jsonl"
        kept += [json.loads(x) for x in para.read_text().splitlines()] if para.exists() else []
        chosen = select_oracle(tasks, kept)
        s = generate(
            chosen,
            work / "oracle",
            OraclePolicy(chosen),
            None,
            corpus(),
            workers=config.TEACHER_WORKERS,
        )
        print(json.dumps(dataclasses.asdict(s)))
        return
    if a.mode == "refilter":  # no API call: recompute kept.jsonl from the raw trajectories
        work = config.DATA_DIR / "teacher" / a.name
        print(json.dumps(refilter(work, load_tasks("train", purpose="teacher"))))
        build_card(work, {"refiltered": True})
        return
    if a.budget_usd <= 0:
        raise SystemExit("--budget-usd is required for pilot and bulk")
    if not is_offpeak(datetime.now(UTC)):
        raise SystemExit("inside a DeepSeek peak window (config.DEEPSEEK_PEAK_UTC): not running")
    tasks = load_tasks("train", purpose="teacher")
    if a.mode == "pilot":
        tasks = pilot_selection(tasks)
        if a.budget_usd > 0.05 or len(tasks) > 20:
            raise SystemExit("pilot is capped at 20 tasks and $0.05 (G1)")
    work = config.DATA_DIR / "teacher" / a.name
    guard = BudgetGuard(config.LEDGER_PATH, config.BUDGET_LIFETIME_USD, a.budget_usd, a.name)
    policy = policy_from_config(MODEL_CONFIG, guard)
    if a.mode == "bulk":
        if a.limit:
            tasks = tasks[: a.limit + len(_finished(work))]  # smoke runs: --limit N new tasks
        why = bulk(
            tasks, work, policy, guard, workers=config.TEACHER_WORKERS, chunk=config.TEACHER_CHUNK,
            gate=config.TEACHER_KEPT_GATE, gate_min_n=config.TEACHER_GATE_MIN_N,
        )  # fmt: skip
        (work / "END.json").write_text(
            json.dumps({"why": why, "at": datetime.now(UTC).isoformat()})
        )
        print(f"bulk ended: {why}", flush=True)
        build_card(work, {"ended": why})
        sys.exit(0 if why in ("complete", "budget") else 2)
    summary = generate(tasks, work, policy, guard, corpus(), offpeak_only=True)
    card = build_card(work, dataclasses.asdict(summary))
    print(json.dumps(dataclasses.asdict(summary), indent=1))
    if a.report_dir:
        a.report_dir.mkdir(parents=True, exist_ok=False)
        for f in ("trajectories.jsonl", "kept.jsonl"):
            if (work / f).exists():
                shutil.copy(work / f, a.report_dir / f)
        shutil.copy(card, a.report_dir / "DATA_CARD.json")


if __name__ == "__main__":
    main()
