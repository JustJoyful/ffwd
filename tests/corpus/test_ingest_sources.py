import json
import re
import shutil

import pytest

from training import config
from training.corpus import ingest_sources as ing
from training.corpus.add_clip import add_clip
from training.taskgen.clips import ClipIndex


@pytest.fixture
def env(corpus, tmp_path):
    """videos/ holding one real source (a 4 s 1080p h264+aac corpus clip) and an empty corpus dir."""
    videos, cdir, work = tmp_path / "videos", tmp_path / "corpus", tmp_path / "work"
    for d in (videos, cdir, work):
        d.mkdir()
    shutil.copy(corpus["h264_aac_1080p"], videos / "src.mp4")
    (cdir / "manifest.json").write_text("[]")
    return videos, cdir, work


def row(**kw):
    base = {
        "id": "cut1", "origin": "downloaded", "src": "src.mp4", "source_url": "https://example.org/src.mp4",
        "licence": "CC BY 3.0", "attribution": "(CC) Someone", "role": "taskgen",
        "tags": ["h264_landscape"], "restricted": False, "synthetic": False, "consent": None,
        "cut": {"start": 0.5, "duration": 2.0},
        "must": {"video_codec": "h264", "audio": True, "min_width": 1920},
    }  # fmt: skip
    return base | kw


def manifest(cdir):
    return json.loads((cdir / "manifest.json").read_text())


def test_cut_row_becomes_a_clip_with_full_provenance(env):
    videos, cdir, work = env
    rec = ing.build_clip(row(restricted=True), videos, cdir, work)
    assert manifest(cdir) == [rec] and (cdir / rec["file"]).exists()
    assert (
        rec["tags"] == ["h264_landscape"] and rec["restricted"] is True and rec["role"] == "taskgen"
    )
    assert rec["origin"] == "downloaded" and rec["attribution"] == "(CC) Someone"
    pv = rec["provenance"]
    assert {"-c", "copy"} <= set(pv["command"]) and "{out}" in pv["command"]
    assert pv["source_sha256"] and pv["cut_start_s"] == 0.5 and pv["ffmpeg_version"]
    assert 1.5 <= rec["probe"]["duration_s"] <= 2.6  # the REAL duration is what the probe records
    assert not list(work.iterdir())  # work files are cleaned up


def test_failed_assertion_writes_nothing(env):
    videos, cdir, work = env
    with pytest.raises(ValueError, match="min_width"):
        ing.build_clip(row(must={"min_width": 5000}), videos, cdir, work)
    assert manifest(cdir) == [] and not list(cdir.glob("cut1*"))


def test_whole_file_row_is_a_byte_copy(env):
    videos, cdir, work = env
    rec = ing.build_clip(
        row(cut=None, origin="own-recording", consent="friend agreed"), videos, cdir, work
    )
    assert (cdir / rec["file"]).read_bytes() == (videos / "src.mp4").read_bytes()
    assert rec["consent"] == "friend agreed" and rec["provenance"]["command"] is None


def test_existing_ids_are_skipped_and_rebuild_reproduces_the_sha(env):
    videos, cdir, work = env
    rec = ing.build_clip(row(), videos, cdir, work)
    assert ing.build_clip(row(), videos, cdir, work) is None and len(manifest(cdir)) == 1
    assert ing.rebuild_sha(rec, videos, cdir, work) == rec["sha256"]
    assert ing.rebuild_verdict(rec, videos, cdir, work) == "identical"
    assert ing.rebuild_verdict(rec | {"sha256": "0" * 64}, videos, cdir, work) == "same-content"


def test_derived_row_runs_its_recorded_command_on_the_parent(env):
    videos, cdir, work = env
    ing.build_clip(row(), videos, cdir, work)
    d = row(
        id="quiet1", origin="derived", synthetic=True, src=None, parent="cut1", cut=None, ext=".mp4",
        ffmpeg=["-i", "{parent}", "-c:v", "copy", "-af", "volume=-25dB", "-c:a", "aac", "{out}"],
        must={"audio": True, "gain_db_vs_parent": [-26.5, -23.5]}, tags=["quiet_audio"],
    )  # fmt: skip
    rec = ing.build_clip(d, videos, cdir, work)
    assert rec["parent"] == "cut1" and rec["synthetic"] is True
    assert any("volume=-25dB" in t for t in rec["provenance"]["command"])
    assert any("cut1" in t for t in rec["provenance"]["command"])


def test_check_must_reports_each_violated_property(env):
    videos, cdir, _ = env
    p = ing.probe(videos / "src.mp4")
    raw = ing.raw_streams(videos / "src.mp4")
    ok = {"video_codec": "h264", "audio": True, "aspect": [1.7, 1.8], "container": "mp4"}
    assert ing.check_must(videos / "src.mp4", p, raw, ok, {}, None) == []
    bad = {"video_codec": "hevc", "audio": False, "aspect": [2.3, 2.5], "rotation_nonzero": True}
    assert len(ing.check_must(videos / "src.mp4", p, raw, bad, {}, None)) == 4


def test_inherent_av_skew_must_be_declared_with_a_tag_and_is_recorded(env, tmp_path):
    import subprocess

    videos, cdir, work = env
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(videos / "src.mp4"), "-itsoffset", "0.5",
         "-i", str(videos / "src.mp4"), "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", str(videos / "skewed.mov")],
        check=True,
    )  # fmt: skip
    with pytest.raises(ValueError, match="av_skew"):
        ing.build_clip(row(id="sk1", src="skewed.mov", cut=None), videos, cdir, work)
    rec = ing.build_clip(
        row(id="sk1", src="skewed.mov", cut=None, tags=["av_skew"]), videos, cdir, work
    )
    assert 450 <= rec["measured_offset_ms"] <= 550


def test_f11_never_draws_av_skew_clips(corpus_records):
    import random

    from training.taskgen.families import SAMPLERS

    out, records = corpus_records
    records = [r | {"tags": [*r.get("tags", []), "av_skew"]} for r in records]
    (out / "manifest.json").write_text(json.dumps(records))
    ci = ClipIndex(out / "manifest.json")
    assert all(SAMPLERS["F11"](random.Random(i), ci) is None for i in range(30))


def test_clip_index_skips_restricted_clips(corpus_records):
    out, records = corpus_records
    records = [records[0] | {"restricted": True}, *records[1:]]
    (out / "manifest.json").write_text(json.dumps(records))
    ci = ClipIndex(out / "manifest.json")
    assert records[0]["id"] not in ci.clips and len(ci.clips) == len(records) - 1


def test_add_clip_stores_tags_offset_and_extra_fields(corpus, tmp_path):
    (tmp_path / "manifest.json").write_text("[]")
    rec = add_clip(
        corpus["h264_aac_1080p"], "x1", "own", "owner", "taskgen", corpus_dir=tmp_path,
        tags=("a_tag",), known_offset_ms=500.0, extra={"origin": "own-recording"},
    )  # fmt: skip
    assert (
        rec["tags"] == ["a_tag"]
        and rec["known_offset_ms"] == 500.0
        and rec["origin"] == "own-recording"
    )


def test_the_committed_source_table_is_well_formed():
    rows = json.loads(ing.SOURCES.read_text())
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    for i, r in enumerate(rows):
        assert re.fullmatch(r"[a-z][a-z0-9_]{0,15}", r["id"]), r["id"]
        assert r["role"] in config.CLIP_ROLES and r["origin"] in ing.ORIGINS
        assert r["licence"].strip() and r["attribution"].strip(), r["id"]
        assert isinstance(r["restricted"], bool) and isinstance(r["synthetic"], bool)
        assert r["synthetic"] == (r["origin"] == "derived")
        if r["origin"] == "derived":
            assert r["parent"] in ids[:i] and r["ffmpeg"], r["id"]  # parent built first
        else:
            assert r["src"] and r["must"], r["id"]
        if r["origin"] == "downloaded":
            assert "source_url" in r  # may be null (Meridian), never absent
