import subprocess

import pytest

from training.env import sandbox
from training.env.executor import execute, output_path_for
from training.env.sandbox import SandboxUnavailable, sandbox_prefix

needs_bwrap = pytest.mark.skipif(not sandbox._works(), reason="bubblewrap unusable here")
TRIM = ["-i", "{in:clip}", "-t", "1", "-c", "copy", "{out:out1}"]
SPEC = {"id": "out1", "kind": "video", "container": "mp4"}


def test_off_is_empty_and_bad_mode_rejected(tmp_path):
    assert sandbox_prefix("off", [tmp_path]) == []
    with pytest.raises(ValueError):
        sandbox_prefix("sometimes", [tmp_path])


def test_require_fails_closed_when_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox, "_works", lambda: False)
    with pytest.raises(SandboxUnavailable):
        sandbox_prefix("require", [tmp_path])


def test_auto_falls_back_when_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox, "_works", lambda: False)
    assert sandbox_prefix("auto", [tmp_path]) == []


def test_execute_in_require_mode_raises_instead_of_running_unsandboxed(
    corpus, tmp_path, monkeypatch
):
    monkeypatch.setattr(sandbox, "_works", lambda: False)
    run = {"action": "run", "args": TRIM, "inputs": ["clip"], "outputs": ["out1"]}
    with pytest.raises(SandboxUnavailable):
        execute(
            run,
            input_paths={"clip": corpus["clip_a"]},
            output_paths={"out1": output_path_for(tmp_path, SPEC)},
            sandbox="require",
        )
    assert not (tmp_path / "out" / "out1.mp4").exists()


@needs_bwrap
def test_sandboxed_ffmpeg_still_works_and_writes_its_output(corpus, tmp_path):
    run = {"action": "run", "args": TRIM, "inputs": ["clip"], "outputs": ["out1"]}
    r = execute(
        run,
        input_paths={"clip": corpus["clip_a"]},
        output_paths={"out1": output_path_for(tmp_path, SPEC)},
        sandbox="require",
    )
    assert r.ok, r.stderr_tail
    assert r.outputs["out1"].stat().st_size > 0


@needs_bwrap
def test_sandbox_has_no_network_and_is_read_only_outside_outputs(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    prefix = sandbox_prefix("require", [out])
    net = subprocess.run(
        [
            *prefix,
            "python3",
            "-I",
            "-c",
            "import socket; socket.create_connection(('1.1.1.1', 53), 2)",
        ],
        capture_output=True,
    )
    assert net.returncode != 0
    ok = subprocess.run([*prefix, "touch", str(out / "x")], capture_output=True)
    bad = subprocess.run([*prefix, "touch", str(tmp_path / "elsewhere")], capture_output=True)
    assert ok.returncode == 0 and bad.returncode != 0


def test_rollout_timeout_kills_a_slow_run_and_leaves_no_output(corpus, tmp_path):
    slow = [
        "-i",
        "{in:clip}",
        "-vf",
        "scale=3840:2160",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "0",
        "{out:out1}",
    ]
    run = {"action": "run", "args": slow, "inputs": ["clip"], "outputs": ["out1"]}
    out = output_path_for(tmp_path, SPEC)
    r = execute(
        run, input_paths={"clip": corpus["h264_aac_1080p"]}, output_paths={"out1": out}, timeout_s=1
    )
    assert r.timed_out and not r.ok and not out.exists()
