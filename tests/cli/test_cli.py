import hashlib
import json
import shutil

from apps.cli.ffmpeg_agent_cli import agent as agent_mod
from apps.cli.ffmpeg_agent_cli.agent import run_job
from apps.cli.ffmpeg_agent_cli.server import TEMPLATE, server_argv

SPEC = {
    "family": ["F1"],
    "outputs": [
        {
            "id": "out1",
            "kind": "video",
            "container": "mp4",
            "time": {"start_s": 2, "end_s": None, "tolerance_s": 0.15},
        }
    ],
}
GOOD = {
    "action": "run",
    "args": ["-ss", "2", "-i", "{in:in1}", "-c", "copy", "{out:out1}"],
    "inputs": ["in1"],
    "outputs": ["out1"],
}
WRONG = {
    "action": "run",
    "args": ["-ss", "9", "-i", "{in:in1}", "-c", "copy", "{out:out1}"],
    "inputs": ["in1"],
    "outputs": ["out1"],
}
FINISH = {"action": "finish", "outputs": ["out1"], "note": "done"}


class Script:
    def __init__(self, replies):
        self.replies, self.seen = [
            json.dumps(r) if not isinstance(r, str) else r for r in replies
        ], []

    def __call__(self, messages):
        self.seen.append(messages)
        return self.replies.pop(0)


def _job(tmp_path, corpus, policy, **kw):
    clip = tmp_path / "in" / "clip.mp4"
    clip.parent.mkdir(exist_ok=True)
    if not clip.exists():
        shutil.copy(corpus["h264_long"], clip)
    args = {
        "out_dir": tmp_path / "out",
        "system_prompt": "SYS",
        "confirm": lambda lines: True,
        "ask": lambda q: "yes",
        "say": lambda s: None,
    }
    return clip, run_job("cut the first 2 seconds", clip, policy, **(args | kw))


def test_end_to_end_with_a_scripted_model_and_real_ffmpeg(tmp_path, corpus):
    clip, r = _job(tmp_path, corpus, Script([{"action": "spec", "spec": SPEC}, GOOD, FINISH]))
    before = hashlib.sha256(clip.read_bytes()).hexdigest()
    assert (
        r.ok
        and r.exit_code == 0
        and r.runs == 1
        and r.output.name == "clip_edited.mp4"
        and r.output.stat().st_size > 0
    )
    assert hashlib.sha256(clip.read_bytes()).hexdigest() == before  # the input is never touched
    assert r.spec == SPEC and r.check["passed"]


def test_second_run_never_overwrites_an_earlier_result(tmp_path, corpus):
    _, a = _job(tmp_path, corpus, Script([{"action": "spec", "spec": SPEC}, GOOD, FINISH]))
    _, b = _job(tmp_path, corpus, Script([{"action": "spec", "spec": SPEC}, GOOD, FINISH]))
    assert a.output != b.output and a.output.exists() and b.output.exists()


def test_rejecting_the_spec_runs_nothing(tmp_path, corpus, monkeypatch):
    calls = []
    monkeypatch.setattr(agent_mod, "execute", lambda *a, **k: calls.append(1))
    policy = Script([{"action": "spec", "spec": SPEC}] * 3)
    _, r = _job(tmp_path, corpus, policy, confirm=lambda lines: "no, 5 seconds")
    assert not r.ok and r.exit_code == 3 and calls == [] and r.output is None
    assert (
        "did not confirm" in policy.seen[1][-1]["content"]
    )  # the model is told why and can revise


def test_a_run_before_the_spec_is_rejected_and_the_failed_check_is_reported_honestly(
    tmp_path, corpus
):
    policy = Script([GOOD, {"action": "spec", "spec": SPEC}, WRONG, WRONG, WRONG, WRONG, WRONG])
    _, r = _job(tmp_path, corpus, policy)
    assert not r.ok and r.output is None and "Nothing was claimed as done" in r.message
    assert (
        r.runs == 4 and r.check["passed"] is False
    )  # RULES §8.1: never claim success without a passing check


def test_unsupported_and_ask_user_paths(tmp_path, corpus):
    _, r = _job(
        tmp_path,
        corpus,
        Script(
            [
                {
                    "action": "unsupported",
                    "reason": "I cannot remove people.",
                    "nearest_supported": None,
                }
            ]
        ),
    )
    assert not r.ok and r.exit_code == 2 and "cannot remove people" in r.message
    asked = []
    policy = Script(
        [
            {"action": "ask_user", "question": "how long?"},
            {"action": "spec", "spec": SPEC},
            GOOD,
            FINISH,
        ]
    )
    _, r = _job(tmp_path, corpus, policy, ask=lambda q: asked.append(q) or "2 seconds")
    assert asked == ["how long?"] and r.ok


def test_server_argv_binds_loopback_only_and_loads_the_agent_template(tmp_path):
    argv = server_argv(tmp_path / "llama-server", tmp_path / "m.gguf", 8123)
    assert argv[argv.index("--host") + 1] == "127.0.0.1" and "0.0.0.0" not in argv
    assert argv[argv.index("--chat-template-file") + 1] == str(TEMPLATE) and "--cache-ram" in argv
