import hashlib
import json
from collections import Counter

import pytest

from training import config
from training.taskgen import splits
from training.taskgen.build import build
from training.taskgen.phrasing_heldout import HELDOUT_STYLES
from training.taskgen.splits import assign_split, is_heldout_combo

TARGETS = {"train": 24, "dev": 5, "test-iid": 5, "test-compositional": 5, "test-phrasing": 5}


@pytest.fixture(scope="module")
def built(tmp_path_factory, corpus_records, monkeypatch_module):
    out_dir, records = corpus_records
    (out_dir / "manifest.json").write_text(json.dumps(records))
    monkeypatch_module.setattr(config, "CORPUS_DIR", out_dir)
    out = tmp_path_factory.mktemp("tasks")
    manifest = build(out, targets=TARGETS, workers=2, batch=30)
    return out, manifest


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


def _load(out, split):
    return [json.loads(x) for x in (out / split / "v1.jsonl").read_text().splitlines()]


def test_build_is_deterministic(built, tmp_path, monkeypatch):
    out, manifest = built
    again = build(tmp_path, targets=TARGETS, workers=2, batch=30)
    assert {s: v["sha256"] for s, v in again["splits"].items()} == {
        s: v["sha256"] for s, v in manifest["splits"].items()
    }


def test_splits_reach_targets_and_manifest_hashes_match_files(built):
    out, manifest = built
    for split, target in TARGETS.items():
        info = manifest["splits"][split]
        assert info["tasks"] >= target * 0.8, (split, info["tasks"])
        assert hashlib.sha256((out / split / "v1.jsonl").read_bytes()).hexdigest() == info["sha256"]


def test_content_keys_are_disjoint_across_splits(built):
    out, _ = built
    keys = {s: {t["content_key"] for t in _load(out, s)} for s in TARGETS}
    for a in TARGETS:
        for b in TARGETS:
            if a < b:
                assert not keys[a] & keys[b], (a, b)


def test_heldout_combos_only_in_test_compositional(built):
    out, _ = built
    for s in TARGETS:
        for t in _load(out, s):
            if t["families"]:
                assert is_heldout_combo(t["families"]) == (s == "test-compositional"), (
                    s,
                    t["families"],
                )


def test_heldout_styles_only_in_test_phrasing(built):
    out, _ = built
    for s in TARGETS:
        styles = {t["style"] for t in _load(out, s)}
        assert (
            (styles <= set(HELDOUT_STYLES))
            if s == "test-phrasing"
            else not (styles & set(HELDOUT_STYLES))
        ), s


def test_test_splits_are_not_readable_for_training_purposes():
    from training.taskgen.loader import SplitAccessError, load_tasks

    for s in config.TEST_SPLITS:
        with pytest.raises(SplitAccessError):
            load_tasks(s, "sft")


def test_every_task_is_graded_consistently(built):
    out, _ = built
    for s in TARGETS:
        for t in _load(out, s):
            flagged = t["flags"]["ambiguous"] or t["flags"]["unsupported"]
            assert (t["gold_spec"] is None) == flagged and (t["reference_runs"] is None) == flagged
            if t["flags"]["unsupported"]:
                assert t["families"] == [] and "nearest_supported" in t
            assert t["difficulty"] == max(1, len(t["families"]))


def test_assignment_is_a_pure_function_of_the_content_key():
    assert assign_split("ab" * 32, ["F1"]) == assign_split("ab" * 32, ["F1"])
    assert assign_split("ab" * 32, ["F3", "F4"]) == "test-compositional"
    buckets = Counter(splits.bucket(f"{i:064x}") // 10 for i in range(2000))
    assert min(buckets.values()) > 120  # roughly uniform
