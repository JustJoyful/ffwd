import json
import shutil
import subprocess
from pathlib import Path

import pytest

from training import config
from training.corpus.add_clip import add_clip
from training.corpus.hub import CorpusIntegrityError, pull_corpus, push_corpus
from training.env.probe import first_packet_pts, probe


def _rec(corpus_records, clip_id):
    return next(r for r in corpus_records[1] if r["id"] == clip_id)


def _video(rec):
    return next(s for s in rec["probe"]["streams"] if s["type"] == "video")


def _audio(rec):
    return next(s for s in rec["probe"]["streams"] if s["type"] == "audio")


def test_every_record_has_tags_and_offset_fields(corpus_records):
    assert len(corpus_records[1]) == 22
    for r in corpus_records[1]:
        assert isinstance(r["tags"], list) and "known_offset_ms" in r


def test_v1_recipes_probe_as_tagged(corpus_records):
    assert _video(_rec(corpus_records, "h264_4x3"))["width"] / 480 == pytest.approx(640 / 480)
    assert _rec(corpus_records, "prores_lite")["probe"]["streams"][0]["codec"] == "prores"
    assert "matroska" in _rec(corpus_records, "h264_mkv")["probe"]["container"]
    mono = _audio(_rec(corpus_records, "h264_mono_44k"))
    assert (mono["channels"], mono["sample_rate"]) == (1, 44100)
    assert _video(_rec(corpus_records, "h264_rot270"))["rotation"] == 270
    assert _rec(corpus_records, "h264_2s")["probe"]["duration_s"] == pytest.approx(2.0, abs=0.1)


def test_vfr_clip_has_irregular_timestamps(corpus_records):
    out, _ = corpus_records
    ts = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pts_time", "-of", "csv=p=0", str(out / "h264_vfr.mp4")],
        capture_output=True, text=True, check=True,
    ).stdout.split()  # fmt: skip
    ts = [x.split(",")[0] for x in ts]
    gaps = {round(float(b) - float(a), 3) for a, b in zip(ts, ts[1:], strict=False)}
    assert len(gaps) >= 2


@pytest.mark.parametrize("clip", ["av_late_500", "av_early_500"])
def test_known_offset_clip_measures_within_tolerance(corpus_records, clip):
    out, _ = corpus_records
    rec = _rec(corpus_records, clip)
    v0 = first_packet_pts(out / rec["file"], "video")
    a0 = first_packet_pts(out / rec["file"], "audio")
    assert abs((a0 - v0) * 1000 - rec["known_offset_ms"]) <= config.OFFSET_TOLERANCE_MS


class FakeApi:
    """Stands in for HfApi: a directory is the remote."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(exist_ok=True)

    def create_repo(self, *a, **k):
        assert k.get("private") is True and k.get("repo_type") == "dataset"

    def upload_file(self, *, path_or_fileobj, path_in_repo, repo_id, repo_type):
        shutil.copy(path_or_fileobj, self.root / path_in_repo)

    def hf_hub_download(self, repo_id, filename, *, repo_type, local_dir):
        dst = Path(local_dir) / f"dl_{filename}"
        shutil.copy(self.root / filename, dst)
        return str(dst)


@pytest.fixture
def small_corpus(tmp_path, corpus_records):
    out, records = corpus_records
    d = tmp_path / "src"
    d.mkdir()
    keep = records[:2]
    for r in keep:
        shutil.copy(out / r["file"], d / r["file"])
    (d / "manifest.json").write_text(json.dumps(keep))
    return d


def test_push_pull_roundtrip_verifies_hashes(tmp_path, small_corpus):
    api = FakeApi(tmp_path / "remote")
    push_corpus(small_corpus, "x/y", api=api)
    paths = pull_corpus("x/y", tmp_path / "dst", api=api)
    assert len(paths) == 2 and all(p.is_file() for p in paths.values())


def test_pull_rejects_tampered_clip(tmp_path, small_corpus):
    import tarfile

    api = FakeApi(tmp_path / "remote")
    push_corpus(small_corpus, "x/y", api=api)
    manifest = json.loads((small_corpus / "manifest.json").read_text())
    victim = manifest[0]["file"]
    (small_corpus / victim).write_bytes(b"tampered")
    with tarfile.open(api.root / "corpus.tar.gz", "w:gz") as t:
        for rec in manifest:
            t.add(small_corpus / rec["file"], arcname=rec["file"])
    with pytest.raises(CorpusIntegrityError):
        pull_corpus("x/y", tmp_path / "dst", api=api)


def test_push_refuses_bytes_that_do_not_match_manifest(tmp_path, small_corpus):
    manifest = json.loads((small_corpus / "manifest.json").read_text())
    (small_corpus / manifest[0]["file"]).write_bytes(b"x")
    with pytest.raises(CorpusIntegrityError):
        push_corpus(small_corpus, "x/y", api=FakeApi(tmp_path / "remote"))


def test_add_clip_requires_licence_and_unique_id(tmp_path, corpus_records):
    out, records = corpus_records
    d = tmp_path / "c"
    d.mkdir()
    (d / "manifest.json").write_text("[]")
    src = out / records[0]["file"]
    with pytest.raises(ValueError, match="licence"):
        add_clip(src, "mine", "  ", "owner", corpus_dir=d)
    rec = add_clip(src, "mine", "own recording", "owner", corpus_dir=d)
    assert probe(d / rec["file"])["duration_s"] > 0
    with pytest.raises(ValueError, match="already exists"):
        add_clip(src, "mine", "own recording", "owner", corpus_dir=d)
