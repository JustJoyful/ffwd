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
