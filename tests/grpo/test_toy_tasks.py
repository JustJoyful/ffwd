import json

import pytest

from training import config
from training.env.checker import check
from training.env.executor import execute, output_path_for
from training.env.probe import probe
from training.protocol import validate
from training.taskgen.toy import make_toy_tasks

SPIKE = [
    json.loads(x) for x in (config.DATA_DIR / "tasks/dev/spike-v0.jsonl").read_text().splitlines()
]
TOY = make_toy_tasks(16, seed=7)


def test_toy_tasks_valid_and_disjoint_from_spike():
    assert len(TOY) == 16 and len({t["id"] for t in TOY}) == 16
    assert all(
        validate("task", t) == [] and t["split"] == "toy" and t["source"] == "toy-v0" for t in TOY
    )
    spike_requests, spike_ids = {t["request"] for t in SPIKE}, {t["id"] for t in SPIKE}
    assert not ({t["request"] for t in TOY} & spike_requests) and not (
        {t["id"] for t in TOY} & spike_ids
    )


def test_toy_tasks_deterministic_by_seed():
    assert make_toy_tasks(16, seed=7) == TOY and make_toy_tasks(16, seed=8) != TOY


@pytest.mark.parametrize("task", TOY[:6], ids=[t["id"] for t in TOY[:6]])
def test_toy_reference_runs_pass(task, corpus, tmp_path):
    gold = task["gold_spec"]["outputs"][0]
    run = task["reference_runs"][0]
    r = execute(
        run,
        input_paths={c: corpus[c] for c in task["inputs"]},
        output_paths={"out1": output_path_for(tmp_path, gold)},
    )
    assert r.ok, r.stderr_tail
    res = check(
        gold, r.outputs["out1"], input_probe=probe(corpus[task["inputs"][0]]), run_args=run["args"]
    )
    assert res["passed"], res
