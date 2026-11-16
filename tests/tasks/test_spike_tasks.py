import json
from collections import Counter

import pytest

from training import config
from training.env.checker import check
from training.env.executor import execute, output_path_for
from training.env.probe import probe
from training.protocol import validate

TASKS = [
    json.loads(line)
    for line in (config.DATA_DIR / "tasks" / "dev" / "spike-v0.jsonl").read_text().splitlines()
]
FAMILIES = [f"F{i}" for i in range(1, 13)]


def test_spike_task_count_and_mix():
    assert len(TASKS) == 50
    assert len({t["id"] for t in TASKS}) == 50
    assert sum(t["flags"]["ambiguous"] for t in TASKS) == 3
    assert sum(t["flags"]["unsupported"] for t in TASKS) == 3
    assert sum(len(t["families"]) >= 2 for t in TASKS) == 10
    single = Counter(
        t["families"][0] for t in TASKS if len(t["families"]) == 1 and not any(t["flags"].values())
    )
    assert all(single[f] >= 2 for f in FAMILIES), single
    assert {t["split"] for t in TASKS} == {"dev"} and {t["source"] for t in TASKS} == {"spike-v0"}


@pytest.mark.parametrize("task", TASKS, ids=[t["id"] for t in TASKS])
def test_all_tasks_schema_valid(task):
    assert validate("task", task) == []
    flagged = task["flags"]["ambiguous"] or task["flags"]["unsupported"]
    assert (task["gold_spec"] is None) == flagged
    assert (task["reference_runs"] is None) == flagged


GRADED = [t for t in TASKS if t["gold_spec"]]


# spike-v0 is frozen. Its s13 gold encodes the pre-v1.2 rotation value (270 for "90 clockwise"), which the
# one-convention checker (spike-v1) reads as 90; the v1 file carries the corrected gold.
V0_SUPERSEDED = {
    "s13-rotate-cw-lossless": "rotation convention changed in checker v1.2 (see spike-v1)"
}


@pytest.mark.parametrize("task", GRADED, ids=[t["id"] for t in GRADED])
def test_reference_runs_pass_gold_spec(task, corpus, tmp_path):
    """Validates the task and the checker together: a hand-written solution must pass its gold spec."""
    if task["id"] in V0_SUPERSEDED:
        pytest.skip(V0_SUPERSEDED[task["id"]])
    gold = {o["id"]: o for o in task["gold_spec"]["outputs"]}
    run = task["reference_runs"][-1]
    result = execute(
        run,
        input_paths={c: corpus[c] for c in task["inputs"]},
        output_paths={oid: output_path_for(tmp_path, o) for oid, o in gold.items()},
    )
    assert result.ok, result.stderr_tail
    probes = [probe(corpus[c]) for c in task["inputs"]]
    for oid, path in result.outputs.items():
        r = check(
            gold[oid],
            path,
            input_probe=probes[0],
            run_args=run["args"],
            input_probes=probes,
            input_paths=[corpus[c] for c in task["inputs"]],
        )
        assert r["passed"], (r["error"], [c for c in r["checks"] if not c["ok"]])
