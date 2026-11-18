import random

import pytest

from training.env.validator import uses_stream_copy_only
from training.taskgen.clips import ClipIndex
from training.taskgen.families import SAMPLERS
from training.taskgen.frag import build_args
from training.taskgen.verify import draft_task_core, verify_task

FAMS = [f"F{i}" for i in range(1, 13)]


@pytest.fixture(scope="module")
def ci(corpus_records):
    out, _ = corpus_records
    return (
        ClipIndex(out / "manifest.json")
        if (out / "manifest.json").exists()
        else _index(out, corpus_records[1])
    )


def _index(out, records):
    import json

    (out / "manifest.json").write_text(json.dumps(records))
    return ClipIndex(out / "manifest.json")


def _drafts(fid, ci, n=4):
    got = []
    for seed in range(60):
        d = SAMPLERS[fid](random.Random(f"{fid}-{seed}"), ci)
        if d is not None:
            got.append(d)
        if len(got) == n:
            break
    return got


def test_all_twelve_families_registered_and_productive(ci):
    assert sorted(SAMPLERS, key=lambda f: int(f[1:])) == FAMS
    for fid in FAMS:
        assert _drafts(fid, ci, 1), f"{fid} never produced a draft in 60 seeds"


@pytest.mark.parametrize("fid", FAMS)
def test_reference_solution_passes_its_gold_spec(fid, ci, corpus_records, tmp_path):
    out, _ = corpus_records
    corpus = {c.id: c.path for c in ci.clips.values()}
    for i, d in enumerate(_drafts(fid, ci, 3)):
        task = draft_task_core(d, ci) | {"id": f"{fid}-{i}"}
        row = verify_task(task, corpus, tmp_path / str(i))
        assert row["passed"], (d.intents, task["reference_runs"][0]["args"], row["failed"])


def test_sampling_is_deterministic(ci):
    a = SAMPLERS["F4"](random.Random(7), ci)
    b = SAMPLERS["F4"](random.Random(7), ci)
    assert (a.inputs, a.spec, a.vf) == (b.inputs, b.spec, b.vf)


def test_size_targets_are_never_infeasible(ci):
    for d in _drafts("F6", ci, 8):
        c = ci[d.inputs[0]]
        assert d.spec["size_max_bytes"] <= 0.5 * c.size_bytes and d.bitrate_kbps >= 150


def test_frame_interval_tasks_stay_off_the_boundary(ci):
    from training.env.checker import expected_frame_range

    for d in _drafts("F7", ci, 8):
        if d.frames_interval:
            lo, hi = expected_frame_range(
                ci[d.inputs[0]].duration_s, d.frames_interval, ci[d.inputs[0]].fps
            )
            assert lo == hi == d.spec["frames"]["expected_count"]


def test_lossless_rotation_reference_is_stream_copy_and_f11_uses_itsoffset(ci):
    for d in _drafts("F5", ci, 12):
        args = build_args(d, {c: True for c in d.inputs})
        assert d.spec.get("lossless") == uses_stream_copy_only(args) or not d.spec.get("lossless")
    f11 = _drafts("F11", ci, 4)
    assert all("-itsoffset" in build_args(d, {c: True for c in d.inputs}) for d in f11)


def test_baked_offset_clips_only_appear_in_f11(ci):
    for fid in FAMS:
        if fid == "F11":
            continue
        for d in _drafts(fid, ci, 6):
            assert not any(ci[c].known_offset_ms for c in d.inputs), (fid, d.inputs)


def test_f3_draws_vp8_webm_clips_as_well_as_vp9(corpus_records, tmp_path):
    """Real WebM sources (Tears of Steel, Big Buck Bunny) are VP8; F3's webm intent must not require VP9."""
    import json

    out, records = corpus_records
    for r in records:
        if r["id"] == "vp9_opus_webm":
            for s in r["probe"]["streams"]:
                if s["type"] == "video":
                    s["codec"] = "vp8"
    (out / "manifest.json").write_text(json.dumps(records))
    index = ClipIndex(out / "manifest.json")
    drafts = [SAMPLERS["F3"](random.Random(i), index) for i in range(80)]
    assert any(
        d is not None and d.intents == ["f3.webm"] and d.slots["fmt"] == "WebM" for d in drafts
    )
