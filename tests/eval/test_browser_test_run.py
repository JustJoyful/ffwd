"""The browser-row driver (eval/browser_test_run.py): frozen string, environment verification, lock ordering. No test data is read."""

import copy
import json
from contextlib import contextmanager

import pytest

from eval import browser_test_run as btr
from training import config


def good_env() -> dict:
    f = btr.FROZEN
    return {
        "mode": "gpu", "model": f["gguf_name"], "n_ctx": f["n_ctx"], "kv_cache": dict(f["kv_cache"]),
        "chromium": f["chromium"], "chromium_args": list(f["chromium_args"]), "playwright": f["playwright"], "wllama": f["wllama"],
        "env": {"libllama": f["libllama"], "gpu": {"vendor": "nvidia", "architecture": "ampere", "isFallbackAdapter": False}},
        "load": {"n_ctx": f["n_ctx"], "multithread": True, "threads": 6},
        "memory_cap": {"cgroup": "/x", "memory_max": "6442450944"},
    }  # fmt: skip


def test_checkpoint_string_is_frozen_and_readable():
    s = btr.checkpoint_string()
    assert s == (
        "grpo-m3-ckpt60-q5_k_m[sha256:bbf439b7]+wllama-4.0.0[libllama-b12637-0b51bb2]"
        "+chromium-159.0.8154.6+webgpu+kv-q8_0-fa+n_ctx8192"
    )
    other = copy.deepcopy(btr.FROZEN) | {"wllama": "4.0.1"}
    assert btr.checkpoint_string(other) != s  # a different runtime is a different lock key


def test_verify_env_accepts_the_frozen_environment():
    assert btr.verify_env(good_env()) == []


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda r: r.update(wllama="4.0.1"), "wllama"),
        (lambda r: r["env"].update(libllama="b1"), "libllama"),
        (lambda r: r.update(chromium="160.0.1.1"), "chromium"),
        (lambda r: r["kv_cache"].update(k="f16"), "kv cache"),
        (lambda r: r.update(n_ctx=4096), "n_ctx"),
        (lambda r: r["env"]["gpu"].update(vendor="intel"), "adapter vendor"),
        (lambda r: r["env"]["gpu"].update(isFallbackAdapter=True), "fallback"),
        (lambda r: r["env"]["gpu"].pop("isFallbackAdapter"), "fallback"),
        (lambda r: r["load"].update(multithread=False), "multithreaded"),
        (lambda r: r["memory_cap"].update(memory_max="max"), "memory cap"),
        (lambda r: r.update(chromium_args=[]), "chromium args"),
    ],
)
def test_verify_env_rejects_any_difference(mutate, needle):
    rec = good_env()
    mutate(rec)
    bad = btr.verify_env(rec)
    assert bad and any(needle in b for b in bad)


def test_pinned_task_hashes_equal_the_manifest():
    manifest = json.loads((config.DATA_DIR / "tasks" / "MANIFEST.json").read_text())["splits"]
    for split, sha in btr.PINNED_TASK_SHA256.items():
        assert manifest[split]["sha256"] == sha


def test_amendment_4_contains_the_frozen_string():
    text = btr.PREREG.read_text()
    assert "Amendment 4" in text and btr.checkpoint_string() in text


@pytest.fixture
def fake_run(tmp_path, monkeypatch):
    """A synthetic test-iid file in a temp DATA_DIR, a fake bridge, and recorders for the lock and the harness."""
    d = tmp_path / "data" / "tasks" / "test-iid"
    d.mkdir(parents=True)
    (d / "v1.jsonl").write_text(json.dumps({"id": "t1", "split": "test-iid"}) + "\n")
    monkeypatch.setattr(btr.config, "DATA_DIR", tmp_path / "data")
    calls: list[str] = []
    state = {"env": good_env()}

    @contextmanager
    def fake_bridge(b):
        b.bridge_dir.mkdir(parents=True, exist_ok=True)
        (b.bridge_dir / "env.json").write_text(json.dumps(state["env"]))
        yield "http://fake"

    monkeypatch.setattr(btr, "serve_bridge", fake_bridge)
    monkeypatch.setattr(btr, "acquire_test_run", lambda *a, **k: calls.append("lock"))
    monkeypatch.setattr(btr, "run_baseline", lambda **k: calls.append("run"))
    monkeypatch.setattr(btr, "load_corpus", lambda: {})
    monkeypatch.setattr(btr, "provenance", lambda: {})
    return tmp_path, calls, state


def test_a_mismatching_environment_aborts_before_the_lock(fake_run):
    root, calls, state = fake_run
    state["env"]["wllama"] = "9.9.9"
    with pytest.raises(SystemExit, match="no lock taken"):
        btr.run_split(root / "root", "test-iid", False, "6G", 8123)
    assert calls == []  # neither locked nor run


def test_the_lock_is_taken_before_the_run(fake_run):
    root, calls, _ = fake_run
    btr.run_split(root / "root", "test-iid", False, "6G", 8123)
    assert calls == ["lock", "run"]


def test_a_partial_run_stops_the_driver(fake_run):
    root, calls, _ = fake_run
    (root / "root" / "runs" / "M3-browser-test-iid").mkdir(parents=True)  # started, no manifest
    with pytest.raises(SystemExit, match="partial run"):
        btr.run_split(root / "root", "test-iid", False, "6G", 8123)
    assert calls == []
