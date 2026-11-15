import json

import pytest

from training import config
from training.grpo.taskfilter import (
    episode_sampler,
    load_table,
    pass_rate_table,
    save_table,
    select_tasks,
)
from training.taskgen.toy import make_toy_tasks

TASKS = [{"id": f"t{i}", "split": "train"} for i in range(7)]
PASSES = {"t0": 0, "t1": 1, "t2": 2, "t3": 6, "t4": 8, "t5": 10, "t6": 5}  # out of K=10


def sampler(task, k):
    return [True] * PASSES[task["id"]] + [False] * (k - PASSES[task["id"]])


def test_default_band_comes_from_config_and_is_20_to_80():
    assert config.PASS_RATE_BAND == (0.2, 0.8)


def test_band_is_inclusive_and_labels_the_reason():
    table = pass_rate_table(TASKS, sampler, k=10, band=(0.2, 0.8), meta={"model": "m"})
    rows = table["tasks"]
    assert {t: r["keep"] for t, r in rows.items()} == {
        "t0": False,
        "t1": False,
        "t2": True,
        "t3": True,
        "t4": True,
        "t5": False,
        "t6": True,
    }
    assert rows["t0"]["reason"] == "too_hard" and rows["t1"]["reason"] == "too_hard"
    assert (
        rows["t5"]["reason"] == "too_easy" and rows["t4"]["reason"] == "in_band"
    )  # 0.8 and 0.2 are kept
    assert table["summary"] == {"total": 7, "kept": 4, "too_easy": 1, "too_hard": 2}
    assert [t["id"] for t in select_tasks(TASKS, table)] == ["t2", "t3", "t4", "t6"]


def test_table_records_what_is_needed_to_reproduce_it(tmp_path):
    table = pass_rate_table(
        TASKS, sampler, k=10, band=(0.1, 0.9), meta={"model": "sft-v1", "seed": 7}
    )
    assert (
        table["meta"]["k"] == 10
        and table["meta"]["band"] == [0.1, 0.9]
        and table["meta"]["model"] == "sft-v1"
    )
    p = save_table(table, tmp_path / "pass_rates.json")
    assert load_table(p) == json.loads(p.read_text()) == table


def test_only_train_or_toy_tasks_may_be_filtered():
    for split in ("dev", "test-iid", "test-real"):
        with pytest.raises(ValueError, match="split"):
            pass_rate_table([{"id": "x", "split": split}], sampler, k=2, band=(0.2, 0.8), meta={})


@pytest.mark.parametrize("band", [(0.8, 0.2), (-0.1, 0.5), (0.2, 1.5)])
def test_bad_bands_are_rejected(band):
    with pytest.raises(ValueError, match="band"):
        pass_rate_table(TASKS, sampler, k=10, band=band, meta={})


def test_selecting_from_an_empty_band_fails_loudly():
    table = pass_rate_table(TASKS[:1], sampler, k=10, band=(0.2, 0.8), meta={})  # t0: 0/10
    with pytest.raises(ValueError, match="no tasks"):
        select_tasks(TASKS[:1], table)


def test_episode_sampler_runs_real_episodes_through_the_checker(corpus, tmp_path):
    tasks = make_toy_tasks(2, seed=5)
    by_request = {t["request"]: t for t in tasks}

    def replay_reference(messages):  # a perfect policy: replay the reference run, then finish
        task = by_request[json.loads(messages[1]["content"])["request"]]
        if len(messages) == 2:
            return json.dumps(task["reference_runs"][0])
        return json.dumps({"action": "finish", "outputs": ["out1"], "note": "ok"})

    refuse = lambda messages: json.dumps({"action": "unsupported", "reason": "no"})  # noqa: E731
    always = episode_sampler(lambda: replay_reference, corpus, tmp_path / "a")(tasks[0], 2)
    never = episode_sampler(lambda: refuse, corpus, tmp_path / "b")(tasks[0], 2)
    assert always == [True, True] and never == [False, False]


def test_apply_filter_selects_in_band_tasks_and_stores_the_table_with_the_run(tmp_path):
    from training.grpo.taskfilter import apply_filter

    table = pass_rate_table(TASKS, sampler, k=10, band=(0.2, 0.8), meta={"model": "m"})
    saved = save_table(table, tmp_path / "pass_rates_in.json")
    run_dir = (
        tmp_path / "does" / "not" / "exist" / "yet"
    )  # the training script creates its dir later than this runs
    kept = apply_filter(TASKS, saved, run_dir)
    assert [t["id"] for t in kept] == ["t2", "t3", "t4", "t6"]
    assert json.loads((run_dir / "pass_rates.json").read_text()) == table
