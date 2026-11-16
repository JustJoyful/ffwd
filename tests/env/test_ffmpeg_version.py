from training.env.ffmpeg_version import ffmpeg_version
from training.taskgen import build


def test_version_parses_and_is_in_the_verification_cache_key(monkeypatch):
    v = ffmpeg_version()
    assert v[0].isdigit()
    core = {"content_key": "k", "reference_runs": [{"x": 1}]}
    a = build._cache_key(core)
    monkeypatch.setattr(build, "ffmpeg_version", lambda: "5.1.1")
    assert build._cache_key(core) != a or v == "5.1.1"
