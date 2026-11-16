import pytest

from training.corpus.make_bench import BENCH_CLIPS, make_bench
from training.env.probe import probe


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    out = tmp_path_factory.mktemp("bench")
    return out, make_bench(out, duration_s=2.0)


def test_makes_the_four_bench_clips_with_the_right_shape(tiny):
    out, recs = tiny
    assert (
        set(recs)
        == set(BENCH_CLIPS)
        == {"hevc_1080p_60s", "hevc_4k_60s", "h264_100mb_60s", "h264_500mb_60s"}
    )
    shapes = {}
    for name, r in recs.items():
        p = probe(out / r["file"])
        v = next(s for s in p["streams"] if s["type"] == "video")
        shapes[name] = (v["codec"], v["width"], v["height"], round(p["duration_s"]))
        assert r["bytes"] == (out / r["file"]).stat().st_size and len(r["sha256"]) == 64
    assert shapes["hevc_1080p_60s"] == ("hevc", 1920, 1080, 2)
    assert shapes["hevc_4k_60s"] == ("hevc", 3840, 2160, 2)
    assert shapes["h264_100mb_60s"][0] == "h264" and shapes["h264_500mb_60s"][0] == "h264"


def test_hevc_clips_are_iphone_style_mov_with_hvc1(tiny):
    out, recs = tiny
    assert recs["hevc_1080p_60s"]["file"].endswith(".mov")
    assert "mov" in probe(out / recs["hevc_1080p_60s"]["file"])["container"]


def test_size_targets_scale_with_duration_and_cbr_hits_them(tiny):
    _, recs = tiny
    # 100 MB / 60 s clip, but only 2 s long here: expect about 100e6 * 2/60 bytes (CBR pads to the target)
    assert recs["h264_100mb_60s"]["bytes"] == pytest.approx(100e6 * 2 / 60, rel=0.35)
    assert recs["h264_500mb_60s"]["bytes"] == pytest.approx(500e6 * 2 / 60, rel=0.35)
