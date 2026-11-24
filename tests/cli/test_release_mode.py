"""The CLI reads ffwd-model.json (D-053): fail closed, verified-marker, manifest runtime flags, legacy warning, too long.
A tiny fake GGUF and a fake llama-server wrapper: no real model, no real server."""

import hashlib
import json
import shutil

import pytest

from apps.cli.ffmpeg_agent_cli import __main__ as cli
from apps.cli.ffmpeg_agent_cli import release as rel_mod
from apps.cli.ffmpeg_agent_cli.agent import context_guard, run_job
from apps.cli.ffmpeg_agent_cli.release import ReleaseRefused, load_release, run_canary
from apps.cli.ffmpeg_agent_cli.server import server_argv
from tests.cli.test_cli import FINISH, GOOD, SPEC, Script
from training import config
from training.env.chat_template import render
from training.protocol import validate

REAL = config.REPO_ROOT / "releases/ffwd-0.6b-v1.0.0/ffwd-model.json"
GGUF = b"not a real gguf"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture
def pkg(tmp_path, monkeypatch):
    """A package with the real manifest's shape, the real prompt and template, and a tiny fake shipped GGUF."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    root = tmp_path / "pkg"
    root.mkdir()
    prompts = config.PROTOCOL_DIR / "prompts"
    shutil.copy(prompts / "system-v1.txt", root / "system-v1.txt")
    shutil.copy(prompts / "chat-template.jinja", root / "chat-template.jinja")
    (root / "m-Q5_K_M.gguf").write_bytes(GGUF)
    m = json.loads(REAL.read_text())
    m["files"] = [f for f in m["files"] if f["role"] in ("shipped", "prompt", "template")]
    for f in m["files"]:
        if f["role"] == "shipped":
            f.update(path="m-Q5_K_M.gguf", sha256=sha(GGUF), size_bytes=len(GGUF))
    system = (root / "system-v1.txt").read_text()
    prompt = render(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": m["canary"]["user_turn"]},
        ],
        add_generation_prompt=True,
    )
    m["canary"] |= {"file_sha256": sha(GGUF), "rendered_prompt_sha256": sha(prompt.encode())}
    assert validate("model", m) == []
    return root, m


def write(root, m):
    (root / "ffwd-model.json").write_text(json.dumps(m))
    return root


def refused(root, text):
    with pytest.raises(ReleaseRefused, match=text):
        load_release(root)


def test_loads_a_valid_package(pkg):
    root, m = pkg
    r = load_release(write(root, m))
    assert r.gguf.name == "m-Q5_K_M.gguf" and r.runtime["n_ctx"] == 8192
    assert r.system_prompt == (config.PROTOCOL_DIR / "prompts/system-v1.txt").read_text()


def test_each_fail_closed_case(pkg):
    root, m = pkg
    refused(root, "cannot read")  # no manifest
    refused(write(root, {**m, "extra": 1}), "schema")
    refused(write(root, {**m, "protocol_version": "0.4.0"}), "protocol_version 0.4.0")
    refused(write(root, {**m, "min_app_version": "1.0.1"}), "needs app version 1.0.1")
    write(root, m)
    gguf = root / "m-Q5_K_M.gguf"
    gguf.write_bytes(GGUF + b"x")  # size differs
    refused(root, "differs from ffwd-model.json")
    gguf.write_bytes(b"X" * len(GGUF))  # same size, other bytes
    refused(root, "differs from ffwd-model.json")
    gguf.write_bytes(GGUF)
    load_release(root)
    (root / "system-v1.txt").write_text("x" * (root / "system-v1.txt").stat().st_size)
    refused(root, "system-v1.txt: differs")
    shutil.copy(config.PROTOCOL_DIR / "prompts/system-v1.txt", root / "system-v1.txt")
    (root / "chat-template.jinja").write_text("y" * (root / "chat-template.jinja").stat().st_size)
    refused(root, "chat-template.jinja: differs")


def test_marker_skips_the_second_hash_and_only_a_full_pass_writes_it(pkg, monkeypatch):
    root, m = pkg
    write(root, m)
    calls = []
    real = rel_mod.sha256_file
    monkeypatch.setattr(rel_mod, "sha256_file", lambda p: calls.append(p.name) or real(p))
    load_release(root)
    assert calls.count("m-Q5_K_M.gguf") == 1
    load_release(root)
    assert calls.count("m-Q5_K_M.gguf") == 1  # marker hit
    (root / "m-Q5_K_M.gguf").write_bytes(
        b"X" * len(GGUF)
    )  # new mtime, same size: hashed again, refused
    refused(root, "differs")
    assert calls.count("m-Q5_K_M.gguf") == 2
    assert len(json.loads(rel_mod._marker_file().read_text())) == 1  # the failed pass wrote nothing


class FakeServer:
    last = None

    def __init__(self, binary, model, ctx, **flags):
        self.model, self.ctx, self.flags = model, ctx, flags
        self.tokens = []
        FakeServer.last = self

    base_url = "http://127.0.0.1:1/v1"

    def __enter__(self):
        return self

    def __exit__(self, *e):
        pass

    def count_tokens(self, text):
        return 100

    def post(self, path, body):
        assert path == "/completion" and body["temperature"] == 0
        return {"tokens": self.tokens}


def run_main(monkeypatch, tmp_path, corpus, *args, replies=None):
    clip = tmp_path / "clip.mp4"
    shutil.copy(corpus["h264_long"], clip)
    seen = {}

    def policy(url, name, key, *, temperature, max_tokens):
        seen.update(temperature=temperature, max_tokens=max_tokens)
        return Script(replies or [{"action": "spec", "spec": SPEC}, GOOD, FINISH])

    monkeypatch.setattr(cli, "LlamaServer", FakeServer)
    monkeypatch.setattr(cli, "ChatPolicy", policy)
    code = cli.main(["cut", str(clip), "--llama-server", "x", "--yes", *args])
    return code, seen


def test_release_run_uses_the_manifest_runtime(pkg, tmp_path, corpus, monkeypatch, capsys):
    root, m = pkg
    write(root, m)
    code, seen = run_main(monkeypatch, tmp_path, corpus, "--release", str(root))
    s = FakeServer.last
    assert code == 0 and s.ctx == 8192 and s.model == root / "m-Q5_K_M.gguf"
    assert s.flags == {"template": root / "chat-template.jinja", "kv": "q8_0", "flash": True}
    assert (
        seen == {"temperature": 0, "max_tokens": 512} and "warning" not in capsys.readouterr().err
    )


def test_manifest_next_to_model_counts_and_a_bad_one_starts_nothing(
    pkg, tmp_path, corpus, monkeypatch, capsys
):
    root, m = pkg
    write(root, m | {"protocol_version": "9.9.9"})
    FakeServer.last = None
    code, _ = run_main(monkeypatch, tmp_path, corpus, "--model", str(root / "m-Q5_K_M.gguf"))
    assert (
        code == 5
        and FakeServer.last is None
        and "protocol_version 9.9.9" in capsys.readouterr().err
    )
    write(root, m)
    code, _ = run_main(monkeypatch, tmp_path, corpus, "--model", str(root / "m-Q5_K_M.gguf"))
    assert code == 0 and FakeServer.last.flags["kv"] == "q8_0"


def test_legacy_model_without_manifest_warns_and_keeps_old_defaults(
    tmp_path, corpus, monkeypatch, capsys
):
    gguf = tmp_path / "bare.gguf"
    gguf.write_bytes(b"x")
    code, seen = run_main(monkeypatch, tmp_path, corpus, "--model", str(gguf))
    err = capsys.readouterr().err
    assert (
        code == 0 and err.count("\n") == 1 and "no ffwd-model.json" in err and "unverified" in err
    )
    assert FakeServer.last.ctx == 4096 and FakeServer.last.flags.keys() == {"template"}
    assert seen["max_tokens"] == 512


def test_canary_pass_and_fail(pkg, tmp_path, corpus, monkeypatch, capsys):
    root, m = pkg
    ids = m["canary"]["expected_token_ids"]
    server = FakeServer(None, None, 1)
    r = load_release(write(root, m))
    server.tokens = ids
    assert run_canary(r, server) == (True, "20 of 20 tokens match")
    server.tokens = ids[:18] + [0, 0]
    assert run_canary(r, server)[0] is True
    server.tokens = ids[:17] + [0] * 3
    assert run_canary(r, server)[0] is False
    FakeServer.tokens = []  # --canary through main: a failing canary starts no job
    code, _ = run_main(monkeypatch, tmp_path, corpus, "--release", str(root), "--canary")
    assert code == 5 and "canary FAILED" in capsys.readouterr().out


def test_server_argv_release_flags(tmp_path):
    a = server_argv(
        tmp_path / "s", tmp_path / "m", 1, 8192, template=tmp_path / "t", kv="q8_0", flash=True
    )
    s = " ".join(a)
    assert "-c 8192 -np 1 --cache-ram 0" in s and "-ctk q8_0 -ctv q8_0" in s and "-fa on" in s
    assert "-ctk" not in server_argv(
        tmp_path / "s", tmp_path / "m", 1
    ) and "-fa" not in server_argv(tmp_path / "s", tmp_path / "m", 1)


def test_over_length_episode_ends_as_too_long_and_never_truncates(tmp_path, corpus):
    sizes = iter([100, 100, 7700])  # turn 3: 7700 + 512 > 8192
    seen = []
    inner = Script([{"action": "spec", "spec": SPEC}, GOOD, FINISH])
    policy = context_guard(inner, lambda text: next(sizes), 8192, 512)
    clip = tmp_path / "clip.mp4"
    shutil.copy(corpus["h264_long"], clip)
    r = run_job("cut", clip, policy, out_dir=tmp_path, system_prompt="SYS", confirm=lambda _l: True,
                ask=lambda q: "", say=seen.append)  # fmt: skip
    assert not r.ok and r.exit_code == 6 and r.output is None and "Too long" in r.message
    assert (
        len(inner.seen) == 2
    )  # the third turn never reached the model; history was not cut to fit
