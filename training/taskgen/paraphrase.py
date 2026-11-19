"""Train paraphrases (plan T11, owner-approved <= $0.30): extra wordings for the SFT data, without re-running the teacher.

For a content that already has kept teacher trajectories, DeepSeek rewords the request (same digits rule and YES/NO
judge as the dev paraphrase check, `eval.paraphrase`); the new wording replaces `request` in the FIRST user message of a
COPY of that trajectory. The teacher's replies are untouched: the answer depends on what is asked, not on how, and the
judge is shown the gold spec, so a paraphrase that changes the meaning is dropped. Train tasks only (the T1 loader);
nothing here can see a test split. New record ids are `<original id>+p<k>` (the SFT build maps them back to the
content key, so a paraphrase is always on the same side of the validation split as its source).

uv run python -m training.taskgen.paraphrase --kept data/teacher/<run>/kept.jsonl --budget-usd 0.30 --name <run id>
"""

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from eval.paraphrase import JUDGE_SYSTEM, PARA_SYSTEM, paraphrase_tasks
from training import config
from training.policies import ChatPolicy
from training.taskgen.loader import load_tasks
from training.teacher.budget import BudgetExceeded, BudgetGuard
from training.teacher.generate import PEAK_MARGIN, is_offpeak

BATCH = 200  # contents per off-peak check


def with_request(rec: dict, request: str, k: int) -> dict:
    """A copy of a trajectory record whose first user message asks `request` instead (same inputs/outputs)."""
    first = json.loads(rec["messages"][1]["content"])
    first["request"] = request
    messages = [
        rec["messages"][0],
        {**rec["messages"][1], "content": json.dumps(first)},
        *rec["messages"][2:],
    ]
    return rec | {
        "task_id": f"{rec['task_id']}+p{k}", "messages": messages, "source": "teacher-paraphrase",
        "paraphrase_of": rec["task_id"], "original_request": first.get("request") and json.loads(rec["messages"][1]["content"])["request"],
    }  # fmt: skip


def rounds(kept: list[dict], tasks_by_id: dict[str, dict], per_content: int) -> list[list[dict]]:
    """Round k holds the k-th kept wording (by id) of every content, so a spend cap thins all contents evenly."""
    by_content = defaultdict(list)
    for r in sorted(kept, key=lambda r: r["task_id"]):
        by_content[tasks_by_id[r["task_id"]]["content_key"]].append(r)
    return [[v[k] for _, v in sorted(by_content.items()) if len(v) > k] for k in range(per_content)]


def paraphrase_train(
    kept: list[dict],
    tasks_by_id: dict[str, dict],
    write: Callable[[str], str],
    judge: Callable[[str], str],
    *,
    per_content: int = 2,
    workers: int = 4,
    may_start: Callable[[], bool] = lambda: True,
) -> tuple[list[dict], list[dict], str | None]:
    """(augmented records, log rows, why it stopped early or None). `may_start` is asked before every batch."""
    out, log, stopped = [], [], None
    for k, rnd in enumerate(rounds(kept, tasks_by_id, per_content), start=1):
        for i in range(0, len(rnd), BATCH):
            if not may_start():
                return out, log, "peak window"
            batch = rnd[i : i + BATCH]

            def one(rec: dict):
                task = tasks_by_id[rec["task_id"]]
                try:
                    return rec, paraphrase_tasks([task], write, judge)
                except BudgetExceeded as e:
                    return rec, e

            with ThreadPoolExecutor(max_workers=workers) as pool:
                for rec, res in pool.map(one, batch):
                    if isinstance(res, BudgetExceeded):
                        stopped = f"budget: {res}"
                        continue
                    kept_tasks, rows = res
                    log += rows
                    if kept_tasks:
                        out.append(with_request(rec, kept_tasks[0]["request"], k))
            if stopped:
                return out, log, stopped
    return out, log, stopped


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kept", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=None, help="default: next to --kept")
    ap.add_argument("--budget-usd", type=float, required=True)
    ap.add_argument("--name", required=True, help="ledger run id")
    ap.add_argument("--per-content", type=int, default=2)
    ap.add_argument("--workers", type=int, default=config.TEACHER_WORKERS)
    a = ap.parse_args(argv)
    if a.budget_usd > 0.30:
        sys.exit("training paraphrases are capped at $0.30 (owner approval, 19 Nov 2026)")
    out_dir = a.out_dir or a.kept.parent
    outs = [out_dir / "paraphrases.jsonl", out_dir / "paraphrase-log.jsonl"]
    if any(p.exists() for p in outs):
        sys.exit(f"refusing to overwrite {[p.name for p in outs if p.exists()]}")
    kept = [json.loads(x) for x in a.kept.read_text().splitlines()]
    tasks_by_id = {t["id"]: t for t in load_tasks("train", purpose="teacher")}
    guard = BudgetGuard(config.LEDGER_PATH, config.BUDGET_LIFETIME_USD, a.budget_usd, a.name)
    body = {"thinking": {"type": "disabled"}}

    def policy(temperature: float, max_tokens: int) -> ChatPolicy:
        return ChatPolicy(
            config.DEEPSEEK_BASE_URL, config.DEEPSEEK_MODEL_ID or "", config.DEEPSEEK_API_KEY_ENV,
            temperature=temperature, max_tokens=max_tokens, extra_body=body, guard=guard,
        )  # fmt: skip

    writer, judge = policy(0.7, 80), policy(0.0, 5)
    aug, log, stopped = paraphrase_train(
        kept, tasks_by_id,
        lambda r: writer([{"role": "system", "content": PARA_SYSTEM}, {"role": "user", "content": r}]),
        lambda p: judge([{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": p}]),
        per_content=a.per_content, workers=a.workers,
        may_start=lambda: is_offpeak(datetime.now(UTC) + PEAK_MARGIN),
    )  # fmt: skip
    outs[0].write_text("".join(json.dumps(r) + "\n" for r in aug))
    outs[1].write_text("".join(json.dumps(r) + "\n" for r in log))
    print(
        f"kept {len(aug)} paraphrased trajectories of {len(log)} tried; spent ${guard.spent(run_only=True):.4f}"
        + (f"; stopped: {stopped}" if stopped else "")
    )


if __name__ == "__main__":
    main()
