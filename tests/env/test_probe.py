from pathlib import Path

import pytest

from training.env.probe import display_size, probe


def test_probe_h264_fields(corpus):
    p = probe(corpus["h264_aac_1080p"])
    assert "mp4" in p["container"]
    assert p["duration_s"] == pytest.approx(4.0, abs=0.1)
    video, audio = p["streams"]
    assert (video["type"], video["codec"], video["width"], video["height"]) == (
        "video",
        "h264",
        1920,
        1080,
    )
    assert video["fps"] == pytest.approx(30)
    assert (audio["type"], audio["codec"]) == ("audio", "aac")


def test_probe_rotation_is_clockwise(corpus):
    # hevc_rot90 was made with `-display_rotation 90` (FFmpeg: counterclockwise 90, ffprobe rotation=90),
    # which players show turned 90 degrees counterclockwise = 270 clockwise (the one convention).
    assert probe(corpus["hevc_rot90"])["streams"][0]["rotation"] == 270


def test_display_size_swaps_on_rotation():
    assert display_size({"width": 1920, "height": 1080, "rotation": 90}) == (1080, 1920)
    assert display_size({"width": 1920, "height": 1080, "rotation": 180}) == (1920, 1080)


def test_probe_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        probe(tmp_path / "nope.mp4")


def test_stream_fps_falls_back_to_r_frame_rate_when_the_average_is_junk():
    from training.env.probe import stream_fps

    assert (
        stream_fps({"avg_frame_rate": "30000/1", "r_frame_rate": "60/1"}) == 60.0
    )  # BBB webm header
    assert stream_fps(
        {"avg_frame_rate": "75960000/1275383", "r_frame_rate": "59/1"}
    ) == pytest.approx(59.56, abs=0.01)
    assert stream_fps({"avg_frame_rate": "0/0", "r_frame_rate": "25/1"}) == 25.0
