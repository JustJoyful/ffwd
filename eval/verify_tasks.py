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
from training.env.checker import check
from training.env.executor import execute, output_path_for
from training.env.probe import probe


def verify_task(task: dict, corpus: dict[str, Path], work: Path) -> dict:
    gold = {o["id"]: o for o in task["gold_spec"]["outputs"]}
    run = task["reference_runs"][-1]
    res = execute(
        run,
        input_paths={c: corpus[c] for c in task["inputs"]},
        output_paths={oid: output_path_for(work, o) for oid, o in gold.items()},
    )
    row: dict = {"task_id": task["id"], "passed": False, "failed": [], "measurements": {}}
    if not res.ok:
        row["failed"] = [f"reference run rejected/failed: {res.stderr_tail[-120:]}"]
        return row
    probes = [probe(corpus[c]) for c in task["inputs"]]
    ok = set(res.outputs) == set(gold)
    for oid, path in res.outputs.items():
        r = check(
            gold[oid],
            path,
            input_probe=probes[0],
            run_args=run["args"],
            input_probes=probes,
            input_paths=[corpus[c] for c in task["inputs"]],
        )
        ok &= r["passed"]
        row["failed"] += [c["field"] for c in r["checks"] if not c["ok"]] + (
            [r["error"]] if r["error"] else []
        )
        row["measurements"] |= {k: v for k, v in r["measurements"].items() if v is not None}
        for c in r["checks"]:
            if c["field"] == "implicit.duration_s":  # evidence for IMPLICIT_DURATION_TOLERANCE_S
                row["measurements"]["implicit_duration_delta_s"] = round(
                    c["actual"] - c["expected"], 3
                )
    row["passed"] = bool(ok)
    return row


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
