import json

import pytest

from training import config
from training.corpus.add_clip import add_clip
from training.taskgen.clip_roles import real_clip_ids, violations
from training.taskgen.clips import ClipIndex


def test_no_test_real_clip_in_any_other_split():
    """The real repo: every data/tasks/**/*.jsonl (incl. spike-v*) outside test-real avoids test-real clips."""
    real = real_clip_ids()
    assert violations(config.DATA_DIR / "tasks", real) == []


def test_a_planted_violation_is_caught(tmp_path):
    (tmp_path / "dev").mkdir()
    (tmp_path / "test-real").mkdir()
    ok = {"id": "a", "inputs": ["synthetic1"]}
    bad = {"id": "b", "inputs": ["synthetic1", "mine1"]}
    (tmp_path / "dev" / "v1.jsonl").write_text(json.dumps(ok) + "\n" + json.dumps(bad) + "\n")
    (tmp_path / "test-real" / "v1.jsonl").write_text(
        json.dumps({"id": "c", "inputs": ["mine1"]}) + "\n"
    )
    assert violations(tmp_path, {"mine1"}) == [(str(tmp_path / "dev" / "v1.jsonl"), "b", "mine1")]


def test_clip_index_skips_test_real_clips(corpus_records, tmp_path):
    out, records = corpus_records
    records = [records[0] | {"role": "test-real"}, *records[1:]]
    (out / "manifest.json").write_text(json.dumps(records))
    ci = ClipIndex(out / "manifest.json")
    assert records[0]["id"] not in ci.clips and len(ci.clips) == len(records) - 1


def test_add_clip_requires_an_explicit_valid_role(corpus, tmp_path):
    src = next(iter(corpus.values()))
    with pytest.raises(ValueError, match="role"):
        add_clip(src, "mine1", "own, CC0", "owner", "whatever", corpus_dir=tmp_path)


def test_no_restricted_clip_in_any_task_file():
    """Licence-unverified clips (manifest `restricted: true`) never feed any generated or hand-written task."""
    records = json.loads((config.CORPUS_DIR / "manifest.json").read_text())
    restricted = {r["id"] for r in records if r.get("restricted")}
    assert restricted  # the guard is not vacuous: meridian_4k is restricted
    assert violations(config.DATA_DIR / "tasks", restricted) == []


def test_adding_a_test_real_clip_changes_no_split_input(corpus_records, tmp_path):
    """Owner rule: new clips are test-real only and must not change train/dev/test-iid/comp/phrasing."""
    import random

    from training.taskgen.build import corpus_hash, draw_candidate

    out, records = corpus_records
    base = out / "manifest.json"
    base.write_text(json.dumps(records))
    extra = records[0] | {
        "id": "newreal1",
        "file": "newreal1.mp4",
        "role": "test-real",
        "sha256": "0" * 64,
    }
    more = out / "manifest_more.json"  # same directory: clip paths must not be what differs
    more.write_text(json.dumps([*records, extra]))
    assert corpus_hash(base) == corpus_hash(more)
    a, b = ClipIndex(base), ClipIndex(more)
    assert sorted(a.clips) == sorted(b.clips)

    def draws(ci):
        return [draw_candidate(random.Random(f"s:{i}"), ci) for i in range(60)]

    assert draws(a) == draws(b)
    restricted = records[1] | {"restricted": True}
    changed = tmp_path / "m2.json"
    changed.write_text(json.dumps([records[0], restricted, *records[2:]]))
    assert corpus_hash(changed) != corpus_hash(
        base
    )  # a restricted clip leaving the pool does change what can be drawn
