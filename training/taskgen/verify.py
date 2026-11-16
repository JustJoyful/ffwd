"""Execute a task's reference solution against its own gold spec (generate-and-verify, plan T7).

A task whose reference fails is a bug in the task or the checker, never a model failure, so it is dropped
(and counted in the build manifest) instead of being emitted. Shared by `eval.verify_tasks` (hand-written tasks).
"""

import hashlib
import json
from pathlib import Path

from training.env.checker import check
from training.env.executor import execute, output_path_for
from training.env.probe import probe
from training.taskgen.clips import ClipIndex
from training.taskgen.frag import Draft, build_args, gold_spec


def content_key(families: list[str], inputs: list[str], spec: dict | None) -> str:
    blob = json.dumps({"f": sorted(families), "i": inputs, "s": spec}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def draft_task_core(d: Draft, ci: ClipIndex) -> dict:
    """gold_spec + reference_runs + families/inputs/difficulty/content_key (no request text yet)."""
    spec = gold_spec(d)
    args = build_args(d, {c: ci[c].has_audio for c in d.inputs})
    run = {"action": "run", "args": args, "inputs": list(d.inputs), "outputs": [d.output_id]}
    return {
        "inputs": list(d.inputs),
        "gold_spec": spec,
        "families": list(d.families),
        "difficulty": len(d.families),
        "reference_runs": [run],
        "content_key": content_key(d.families, d.inputs, spec),
    }


def verify_task(task: dict, corpus: dict[str, Path], work: Path) -> dict:
    gold = {o["id"]: o for o in task["gold_spec"]["outputs"]}
    run = task["reference_runs"][-1]
    res = execute(
        run,
        input_paths={c: corpus[c] for c in task["inputs"]},
        output_paths={oid: output_path_for(work, o) for oid, o in gold.items()},
    )
    row: dict = {"task_id": task.get("id", "?"), "passed": False, "failed": [], "measurements": {}}
    if not res.ok:
        row["failed"] = [f"reference run rejected/failed: {res.stderr_tail[-160:]}"]
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
