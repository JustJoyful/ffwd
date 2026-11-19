import json
import random
from pathlib import Path

import pytest

from training import config
from training.taskgen import hard, phrasing, recovery
from training.taskgen.phrasing_heldout import HELDOUT_STYLES
from training.taskgen.splits import assign_split
from training.taskgen.verify import verify_task

TEST_SPLIT_NAMES = ("test-iid", "test-compositional", "test-phrasing", "test-real")


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module")
def pool(corpus_records, monkeypatch_module):
    """A small hard pool built on the synthetic corpus WHILE every read of a test-split path raises (criterion (c))."""
    out_dir, records = corpus_records
    (out_dir / "manifest.json").write_text(json.dumps(records))
    reads: list[str] = []
    real_read_text, real_read_bytes = Path.read_text, Path.read_bytes

    def guard(real):
        def wrapped(self, *a, **k):
            if any(n in str(self) for n in TEST_SPLIT_NAMES):
                reads.append(str(self))
                raise AssertionError(f"test-split file read: {self}")
            return real(self, *a, **k)

        return wrapped

    monkeypatch_module.setattr(Path, "read_text", guard(real_read_text))
    monkeypatch_module.setattr(Path, "read_bytes", guard(real_read_bytes))
    tasks, stats = hard.build_pool(12, workers=2, batch=20, manifest=out_dir / "manifest.json")
    monkeypatch_module.setattr(Path, "read_text", real_read_text)
    monkeypatch_module.setattr(Path, "read_bytes", real_read_bytes)
    assert not reads
    return tasks, stats


def test_pool_tasks_are_train_only_in_train_styles_with_train_bucket_contents(pool):
    tasks, _ = pool
    assert len(tasks) == 12 and len({t["id"] for t in tasks}) == 12
    for t in tasks:
        assert t["split"] == "train" and t["source"].endswith("-hard")
        assert assign_split(t["content_key"], t["families"], config.TASKGEN_SEED) == "train"
        assert t["style"] in phrasing.TRAIN_STYLES and t["style"] not in HELDOUT_STYLES
        assert not t["flags"]["ambiguous"] and not t["flags"]["unsupported"]


def test_pool_is_reweighted_toward_multi_family_tasks(pool):
    tasks, _ = pool
    assert max(len(t["families"]) for t in tasks) >= 3
    assert hard.combo_weight(("F2", "F9", "F10")) > hard.combo_weight(("F1", "F3", "F12")) >= 1


def test_pool_excludes_keys_it_was_told_about(pool, corpus_records):
    tasks, _ = pool
    again, _ = hard.build_pool(
        3, workers=2, batch=10, existing_keys=frozenset(t["content_key"] for t in tasks)
    )
    assert not ({t["content_key"] for t in tasks} & {t["content_key"] for t in again})


def test_every_recovery_start_fails_when_perturbed_and_its_reference_passes(pool, corpus, tmp_path):
    """Criterion (b): re-verified here independently of the generator's own check."""
    tasks, _ = pool
    rows = []
    for t in tasks:
        r = recovery.make_recovery(t, corpus, tmp_path / t["id"], random.Random(t["id"]))
        if r:
            rows.append((t, r))
    assert len(rows) >= 3, "the operators found a verified perturbation for too few tasks"
    for t, r in rows:
        ref = verify_task(t, corpus, tmp_path / ("ref-" + t["id"]))
        assert ref["passed"], (t["id"], ref["failed"])  # every reference passes
        run = t["reference_runs"][-1] | {"args": r["perturbed_args"]}
        assert run["args"] != t["reference_runs"][-1]["args"]
        bad = verify_task(t | {"reference_runs": [run]}, corpus, tmp_path / ("bad-" + t["id"]))
        assert not bad["passed"] and bad["failed"], (
            t["id"],
            r["operator"],
        )  # every perturbation fails
        assert not any(
            f.startswith("reference run") for f in bad["failed"]
        )  # it ran; the checker said no
        assert r["failed"] == sorted(set(bad["failed"])) and r["reference_passed"] is True
        spec, run_action = map(json.loads, r["opening"])
        assert spec == {"action": "spec", "spec": t["gold_spec"]}
        assert run_action["action"] == "run" and run_action["args"] == r["perturbed_args"]
        assert r["task_id"] == t["id"] + "-rec" and len(r["opening"]) == 2


def test_operators_change_only_their_target_and_decline_when_inapplicable():
    a = [
        "-ss",
        "0",
        "-t",
        "2",
        "-i",
        "{in:c}",
        "-vf",
        "scale=1080:1920,crop=1080:1080",
        "-an",
        "{out:out1}",
    ]
    assert recovery.halve_t(a)[3] == "1" and recovery.halve_t(a)[:3] == a[:3]
    assert "-an" not in recovery.drop_an(a) and len(recovery.drop_an(a)) == len(a) - 1
    assert recovery.shift_ss(a)[1] == "1"
    scaled = dict(recovery.OPERATORS)["scale_wrong"](a)
    assert "scale=540:960" in scaled[7] and "crop=1080:1080" in scaled[7]
    assert recovery.drop_af(a) is None and recovery.bitrate_up(a) is None  # nothing to perturb
    assert recovery.bitrate_up(["-b:v", "600k"]) == ["-b:v", "2400k"]
    assert a == [
        "-ss",
        "0",
        "-t",
        "2",
        "-i",
        "{in:c}",
        "-vf",
        "scale=1080:1920,crop=1080:1080",
        "-an",
        "{out:out1}",
    ]


def test_opening_policy_replays_the_opening_then_defers_to_the_policy():
    task_msg = json.dumps({"request": "make it small", "inputs": [{"id": "clip_a"}]})
    head = [{"role": "system", "content": "s"}, {"role": "user", "content": task_msg}]
    calls = []

    def policy(messages):
        calls.append(len(messages))
        return "POLICY"

    p = recovery.OpeningPolicy(policy, {("make it small", ("clip_a",)): ["SPEC", "RUN"]})
    msgs = list(head)
    assert p(msgs) == "SPEC" and not calls
    msgs += [{"role": "assistant", "content": "SPEC"}, {"role": "user", "content": "{}"}]
    assert p(msgs) == "RUN" and not calls
    msgs += [{"role": "assistant", "content": "RUN"}, {"role": "user", "content": "{}"}]
    assert p(msgs) == "POLICY" and calls == [6]
    other = [head[0], {"role": "user", "content": json.dumps({"request": "x", "inputs": []})}]
    assert p(other) == "POLICY"  # a task without an opening is untouched


def test_recovery_refuses_test_splits(corpus, tmp_path):
    t = {
        "id": "x",
        "split": "test-iid",
        "flags": {"ambiguous": False, "unsupported": False},
        "reference_runs": [{}],
    }
    with pytest.raises(PermissionError):
        recovery.make_recovery(t, corpus, tmp_path, random.Random(0))
