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
