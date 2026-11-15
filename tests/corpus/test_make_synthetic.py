import hashlib

from training.protocol import validate


def test_make_corpus_records_valid_probe_and_hash(corpus_records):
    out, records = corpus_records
    assert len(records) == 12
    for r in records:
        path = out / r["file"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == r["sha256"]
        assert validate("probe", r["probe"]) == [], r["id"]


def _by_id(records, clip_id):
    return next(r for r in records if r["id"] == clip_id)


def test_hevc_rot90_has_rotation_90(corpus_records):
    video = _by_id(corpus_records[1], "hevc_rot90")["probe"]["streams"][0]
    assert video["codec"] == "hevc"
    assert video["rotation"] == 90


def test_noaudio_has_no_audio_stream(corpus_records):
    streams = _by_id(corpus_records[1], "h264_noaudio")["probe"]["streams"]
    assert [s["type"] for s in streams] == ["video"]


def test_ensure_corpus_regenerates_when_media_missing(tmp_path):
    # A git clone has the tracked manifest but none of the (gitignored) media: regenerate.
    import json

    from training.corpus.make_synthetic import DERIVED, RECIPES, ensure_corpus

    names = {k: v[0] for k, v in RECIPES.items()} | {k: v[0] for k, v in DERIVED.items()}
    (tmp_path / "manifest.json").write_text(
        json.dumps([{"id": k, "file": f} for k, f in names.items()])
    )
    corpus = ensure_corpus(tmp_path)
    assert corpus["clip_a"].is_file() and corpus["clip_a"].parent == tmp_path
    assert len(corpus) == 12
    before = corpus["clip_a"].stat().st_mtime_ns
    assert (
        ensure_corpus(tmp_path)["clip_a"].stat().st_mtime_ns == before
    )  # complete corpus: no rebuild


def test_ensure_corpus_subset_generates_only_requested(tmp_path):
    from training.corpus.make_synthetic import ensure_corpus

    corpus = ensure_corpus(tmp_path, ids={"clip_a"})
    assert set(corpus) == {"clip_a"} and corpus["clip_a"].is_file()
    assert sorted(p.name for p in tmp_path.glob("*.mp4")) == ["clip_a.mp4"]
