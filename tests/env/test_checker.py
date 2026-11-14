import pytest

from training.env.checker import check
from training.env.executor import execute, output_path_for
from training.env.probe import probe
from training.protocol import validate


def _make(tmp_path, corpus, clip, args, out_spec):
    outs = {out_spec["id"]: output_path_for(tmp_path, out_spec)}
    run = {"action": "run", "args": args, "inputs": ["clip"], "outputs": [out_spec["id"]]}
    r = execute(run, input_paths={"clip": corpus[clip]}, output_paths=outs)
    assert r.ok, r.stderr_tail
    return r.outputs[out_spec["id"]], probe(corpus[clip])


def _video(**fields):
    return {"id": "out1", "kind": "video", "container": "mp4", **fields}


def _failed_fields(result):
    return [c["field"] for c in result["checks"] if not c["ok"]]


def test_trim_passes_gold_spec(tmp_path, corpus):
    spec = _video(time={"start_s": 2, "end_s": 5, "tolerance_s": 0.1})
    args = ["-ss", "2", "-i", "{in:clip}", "-t", "3", "-c", "copy", "{out:out1}"]
    out, inp = _make(tmp_path, corpus, "h264_long", args, spec)
    r = check(spec, out, input_probe=inp, run_args=args)
    assert validate("check", r) == []
    assert r["passed"], r
    assert r["measurements"]["re_encoded"] is False


def test_wrong_height_fails_with_field_detail(tmp_path, corpus):
    spec = _video(video={"height": 1920})
    args = [
        "-i",
        "{in:clip}",
        "-vf",
        "scale=-2:720",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "{out:out1}",
    ]
    out, inp = _make(tmp_path, corpus, "clip_a", args, spec)
    r = check(spec, out, input_probe=inp, run_args=args)
    assert not r["passed"]
    assert _failed_fields(r) == ["video.height"]


def test_rotated_display_dims_pass(tmp_path, corpus):
    spec = {
        "id": "out1",
        "kind": "video",
        "container": "mov",
        "video": {"width": 1080, "height": 1920, "rotation": 90},
    }
    args = ["-i", "{in:clip}", "-c", "copy", "{out:out1}"]
    out, inp = _make(tmp_path, corpus, "hevc_rot90", args, spec)
    r = check(spec, out, input_probe=inp, run_args=args)
    assert r["passed"], r


def test_lossless_fails_when_reencoded(tmp_path, corpus):
    spec = _video(lossless=True)
    args = [
        "-i",
        "{in:clip}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "copy",
        "{out:out1}",
    ]
    out, inp = _make(tmp_path, corpus, "clip_a", args, spec)
    r = check(spec, out, input_probe=inp, run_args=args)
    assert _failed_fields(r) == ["lossless"]


def test_frames_every_2s(tmp_path, corpus):
    spec = {
        "id": "frames",
        "kind": "image_sequence",
        "frames": {"interval_s": 2, "expected_count": None, "format": "png"},
    }
    args = ["-i", "{in:clip}", "-vf", "fps=1/2", "{out:frames}"]
    out, inp = _make(tmp_path, corpus, "h264_25fps_720p", args, spec)
    r = check(spec, out, input_probe=inp, run_args=args)
    assert r["passed"], r
    assert r["measurements"]["frame_count"] == pytest.approx(5, abs=1)


def test_frames_wrong_count_fails(tmp_path, corpus):
    spec = {
        "id": "frames",
        "kind": "image_sequence",
        "frames": {"expected_count": 20, "format": "png"},
    }
    args = ["-i", "{in:clip}", "-vf", "fps=1/2", "{out:frames}"]
    out, inp = _make(tmp_path, corpus, "h264_25fps_720p", args, spec)
    assert _failed_fields(check(spec, out, input_probe=inp, run_args=args)) == [
        "frames.expected_count"
    ]


def test_audio_absent_and_codec(tmp_path, corpus):
    spec = _video(audio={"present": False})
    args = ["-i", "{in:clip}", "-an", "-c:v", "copy", "{out:out1}"]
    out, inp = _make(tmp_path, corpus, "clip_a", args, spec)
    assert check(spec, out, input_probe=inp, run_args=args)["passed"]
    spec_bad = _video(audio={"present": True, "codec": "aac"})
    r = check(spec_bad, out, input_probe=inp, run_args=args)
    assert set(_failed_fields(r)) == {"audio.present", "audio.codec"}


def test_size_and_codec(tmp_path, corpus):
    spec = _video(size_max_bytes=10_000_000, video={"codec": "h264", "pix_fmt": "yuv420p"})
    args = ["-i", "{in:clip}", "-c", "copy", "{out:out1}"]
    out, inp = _make(tmp_path, corpus, "hevc_iphone", args, spec)
    assert _failed_fields(check(spec, out, input_probe=inp, run_args=args)) == ["video.codec"]


def test_empty_output_fails_not_raises(tmp_path, corpus):
    out = tmp_path / "empty.mp4"
    out.write_bytes(b"")
    r = check(_video(), out, input_probe=probe(corpus["clip_a"]), run_args=["-c", "copy"])
    assert r["passed"] is False and r["error"]
    assert validate("check", r) == []


def test_header_only_output_fails(tmp_path, corpus):
    # FFmpeg exits 0 for -t 0 but the file holds only a header.
    spec = _video()
    args = ["-i", "{in:clip}", "-t", "0", "-c", "copy", "-f", "mp4", "{out:out1}"]
    out, inp = _make(tmp_path, corpus, "clip_a", args, spec)
    r = check(spec, out, input_probe=inp, run_args=args)
    assert r["passed"] is False and r["error"]


def test_null_fields_unconstrained(tmp_path, corpus):
    spec = {
        "id": "out1",
        "kind": "video",
        "container": None,
        "video": None,
        "audio": None,
        "time": None,
        "size_max_bytes": None,
        "frames": None,
        "lossless": None,
    }
    args = ["-i", "{in:clip}", "-c", "copy", "{out:out1}"]
    out, inp = _make(tmp_path, corpus, "vp9_opus_webm", args, {**spec, "container": "webm"})
    assert check(spec, out, input_probe=inp, run_args=args)["passed"]


def test_loudness_target(tmp_path, corpus):
    spec = _video(audio={"loudness_lufs": -16})
    args = ["-i", "{in:clip}", "-af", "loudnorm=I=-16", "-c:v", "copy", "-c:a", "aac", "{out:out1}"]
    out, inp = _make(tmp_path, corpus, "h264_quiet", args, spec)
    r = check(spec, out, input_probe=inp, run_args=args)
    assert r["passed"], r
    assert r["measurements"]["loudness_lufs"] == pytest.approx(-16, abs=2)
    untouched = _make(
        tmp_path / "b", corpus, "h264_quiet", ["-i", "{in:clip}", "-c", "copy", "{out:out1}"], spec
    )
    assert _failed_fields(check(spec, untouched[0], input_probe=inp, run_args=["-c", "copy"])) == [
        "audio.loudness_lufs"
    ]


def test_audio_offset_measured_from_start_times(tmp_path, corpus):
    spec = _video(audio={"offset_ms": -500})  # audio 500 ms earlier relative to video
    args = [
        "-i",
        "{in:clip}",
        "-itsoffset",
        "0.5",
        "-i",
        "{in:clip2}",
        "-map",
        "1:v",
        "-map",
        "0:a",
        "-c",
        "copy",
        "{out:out1}",
    ]
    outs = {"out1": output_path_for(tmp_path, spec)}
    from training.env.executor import execute as ex

    r = ex(
        {"action": "run", "args": args, "inputs": ["clip", "clip2"], "outputs": ["out1"]},
        input_paths={"clip": corpus["clip_a"], "clip2": corpus["clip_a"]},
        output_paths=outs,
    )
    assert r.ok, r.stderr_tail
    res = check(spec, r.outputs["out1"], input_probe=probe(corpus["clip_a"]), run_args=args)
    assert res["passed"], res
    in_sync = check(
        spec, corpus["clip_a"], input_probe=probe(corpus["clip_a"]), run_args=["-c", "copy"]
    )
    assert _failed_fields(in_sync) == ["audio.offset_ms"]


def test_loudness_measurement_failure_fails_check_not_raises(tmp_path, corpus, monkeypatch):
    import subprocess

    from training.env import checker as checker_mod

    real_run = subprocess.run

    def hang_on_ebur128(argv, **k):
        if any("ebur128" in a for a in argv):
            raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)
        return real_run(argv, **k)

    monkeypatch.setattr(checker_mod.subprocess, "run", hang_on_ebur128)
    spec = _video(audio={"loudness_lufs": -16})
    r = check(spec, corpus["clip_a"], input_probe=probe(corpus["clip_a"]), run_args=["-c", "copy"])
    assert r["passed"] is False
    assert _failed_fields(r) == ["audio.loudness_lufs"]
