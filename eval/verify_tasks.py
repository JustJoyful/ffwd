"""Check that every task's hand-written reference solution passes its own gold spec (task + checker agree).

uv run python -m eval.verify_tasks data/tasks/dev/spike-v1.jsonl [--json out.json]

Run this on every new or edited task BEFORE any system is evaluated on it: a task whose reference fails
is a bug in the task or the checker, never a model failure. Ambiguous/unsupported tasks have no reference
and are skipped. Prints the measurements that justify the tolerances in training/config.py.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from eval.run_baseline import load_corpus
from training.taskgen.verify import verify_task


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    tasks = [json.loads(x) for x in a.tasks.read_text().splitlines()]
    corpus = load_corpus()
    rows = []
    with tempfile.TemporaryDirectory(prefix="verify-") as d:
        for i, t in enumerate(tasks):
            if not t["gold_spec"] or not t["reference_runs"]:
                continue
            rows.append(verify_task(t, corpus, Path(d) / f"{i:03d}"))
            r = rows[-1]
            print(("PASS " if r["passed"] else "FAIL ") + r["task_id"], r["failed"] or "")
    bad = [r for r in rows if not r["passed"]]
    print(f"{len(rows) - len(bad)}/{len(rows)} reference solutions pass")
    if a.json:
        a.json.write_text(json.dumps(rows, indent=1) + "\n")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
