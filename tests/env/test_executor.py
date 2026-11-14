import subprocess

from training import config
from training.env.executor import execute, output_path_for


def _run(args, inputs=("clip",), outputs=("out1",)):
    return {"action": "run", "args": args, "inputs": list(inputs), "outputs": list(outputs)}


def _out(tmp_path, out_id="out1", kind="video", container="mp4", fmt=None):
    spec = {"id": out_id, "kind": kind, "container": container, "frames": {"format": fmt}}
    return {out_id: output_path_for(tmp_path, spec)}


def test_rejected_run_never_spawns(tmp_path, monkeypatch, corpus):
    def boom(*a, **k):
        raise AssertionError("subprocess must not run for a rejected action")

    monkeypatch.setattr(subprocess, "run", boom)
    r = execute(
        _run(["-i", "http://x/a.mp4", "{out:out1}"]),
        input_paths={"clip": corpus["h264_long"]},
        output_paths=_out(tmp_path),
    )
    assert not r.ok and r.rejected and r.returncode is None


def test_stream_copy_trim_produces_output(tmp_path, corpus):
    outs = _out(tmp_path)
    r = execute(
        _run(["-ss", "2", "-i", "{in:clip}", "-t", "3", "-c", "copy", "{out:out1}"]),
        input_paths={"clip": corpus["h264_long"]},
        output_paths=outs,
    )
    assert r.ok, r.stderr_tail
    assert r.outputs["out1"] == outs["out1"] and outs["out1"].stat().st_size > 0
    assert outs["out1"].parent == tmp_path / "out"


def test_image_sequence_output_dir(tmp_path, corpus):
    outs = _out(tmp_path, "frames", "image_sequence", None, "png")
    r = execute(
        _run(["-i", "{in:clip}", "-vf", "fps=1/2", "{out:frames}"], outputs=["frames"]),
        input_paths={"clip": corpus["h264_25fps_720p"]},
        output_paths=outs,
    )
    assert r.ok, r.stderr_tail
    assert r.outputs["frames"] == tmp_path / "out" / "frames"
    assert len(list(r.outputs["frames"].glob("*.png"))) >= 5


def test_nonzero_exit_returns_stderr_tail(tmp_path, corpus):
    outs = _out(tmp_path)
    r = execute(
        _run(["-i", "{in:clip}", "-map", "0:a", "-c", "copy", "{out:out1}"]),
        input_paths={"clip": corpus["h264_noaudio"]},
        output_paths=outs,
    )
    assert not r.ok and r.rejected is None
    assert r.returncode not in (0, None)
    assert 0 < len(r.stderr_tail) <= config.STDERR_TAIL_CHARS
    assert not outs["out1"].exists()


def test_timeout_deletes_partial(tmp_path, corpus):
    outs = _out(tmp_path)
    args = ["-i", "{in:clip}", "-c:v", "libx265", "-preset", "slow", "{out:out1}"]
    r = execute(
        _run(args), input_paths={"clip": corpus["h264_long"]}, output_paths=outs, timeout_s=1
    )
    assert r.timed_out and not r.ok
    assert not outs["out1"].exists()


def test_size_cap_deletes_output(tmp_path, corpus):
    outs = _out(tmp_path)
    r = execute(
        _run(["-i", "{in:clip}", "-c", "copy", "{out:out1}"]),
        input_paths={"clip": corpus["h264_long"]},
        output_paths=outs,
        max_output_bytes=1000,
    )
    assert not r.ok and "size cap" in r.stderr_tail
    assert not outs["out1"].exists()


def test_exit_zero_but_missing_output_fails(tmp_path, corpus, monkeypatch):
    # FFmpeg "succeeds" but writes nothing: must still be a failed run.
    monkeypatch.setattr(
        subprocess, "run", lambda argv, **k: subprocess.CompletedProcess(argv, 0, b"", b"")
    )
    r = execute(
        _run(["-i", "{in:clip}", "-c", "copy", "{out:out1}"]),
        input_paths={"clip": corpus["h264_long"]},
        output_paths=_out(tmp_path),
    )
    assert not r.ok and "missing or empty output" in r.stderr_tail
