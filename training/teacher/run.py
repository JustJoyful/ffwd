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
from datetime import UTC, datetime
from pathlib import Path

from training import config
from training.policies import policy_from_config
from training.taskgen.clips import visible_records
from training.taskgen.loader import load_tasks
from training.teacher.budget import BudgetGuard
from training.teacher.datacard import build_card
from training.teacher.generate import generate, is_offpeak

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


def corpus() -> dict[str, Path]:
    return {r["id"]: config.CORPUS_DIR / r["file"] for r in visible_records()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["pilot", "bulk"])
    ap.add_argument("--name", required=True, help="unique run name (also the ledger run id)")
    ap.add_argument("--budget-usd", type=float, required=True)
    ap.add_argument(
        "--limit", type=int, default=None, help="bulk: stop after this many new episodes"
    )
    ap.add_argument(
        "--report-dir", type=Path, default=None, help="pilot: where to copy the small artifacts"
    )
    a = ap.parse_args()
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
    summary = generate(
        tasks, work, policy, guard, corpus(), offpeak_only=True, max_episodes=a.limit if a.mode == "bulk" else None
    )  # fmt: skip
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
