from types import SimpleNamespace

import pytest

from training import config
from training.policies import ChatPolicy
from training.teacher.budget import BudgetGuard


class FakeClient:
    def __init__(self, calls, events):
        self.calls, self.events = calls, events
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.events.append("create")
        self.calls.append(kw)
        usage = SimpleNamespace(
            model_dump=lambda: {
                "prompt_tokens": 100,
                "prompt_cache_hit_tokens": 60,
                "prompt_cache_miss_tokens": 40,
                "completion_tokens": 20,
            }
        )
        msg = SimpleNamespace(content='{"action":"finish","outputs":[],"note":""}')
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)


@pytest.fixture
def priced(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_MODEL_ID", "test-model")


def _policy(tmp_path, monkeypatch, dry_run=False):
    calls, events = [], []
    guard = BudgetGuard(tmp_path / "l.jsonl", 1.0, 0.25, "r", dry_run=dry_run)
    for name in ("reserve", "settle"):
        orig = getattr(guard, name)
        monkeypatch.setattr(
            guard, name, lambda *a, _o=orig, _n=name: (events.append(_n), _o(*a))[1]
        )
    p = ChatPolicy("http://x", "m", None, max_tokens=64, guard=guard)
    p._client = FakeClient(calls, events)
    return p, guard, calls, events


def test_chat_policy_uses_guard_around_call(tmp_path, monkeypatch, priced):
    p, guard, calls, events = _policy(tmp_path, monkeypatch)
    out = p([{"role": "user", "content": "hi"}])
    assert "finish" in out
    assert events == ["reserve", "create", "settle"]
    assert calls[0]["temperature"] == 0.0 and calls[0]["max_tokens"] == 64
    assert guard.spent() == pytest.approx((60 * 0.006 + 40 * 0.3 + 20 * 1.2) / 1e6)
    assert guard.cache_hit_ratio() == pytest.approx(0.6)


def test_dry_run_never_calls_client(tmp_path, monkeypatch, priced):
    p, guard, calls, _ = _policy(tmp_path, monkeypatch, dry_run=True)
    p([{"role": "user", "content": "hi"}])
    assert calls == [] and guard.spent() == 0


def test_unguarded_local_policy_needs_no_pricing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_MODEL_ID", None)
    p = ChatPolicy("http://localhost:8080/v1", "qwen", None, max_tokens=64, guard=None)
    calls = []
    p._client = FakeClient(calls, [])
    p([{"role": "user", "content": "hi"}])
    assert len(calls) == 1


def test_policy_from_config_paid_requires_guard_and_pricing(tmp_path, monkeypatch):
    from training.policies import policy_from_config
    from training.teacher.budget import BudgetConfigError

    cfg = config.REPO_ROOT / "eval" / "configs"
    with pytest.raises(ValueError):
        policy_from_config(cfg / "deepseek-v4-flash.toml", None)
    monkeypatch.setattr(config, "DEEPSEEK_MODEL_ID", None)
    with pytest.raises(BudgetConfigError):
        policy_from_config(cfg / "deepseek-v4-flash.toml", BudgetGuard(tmp_path / "l", 1, 1, "r"))
    local = policy_from_config(cfg / "qwen3-0.6b.toml", None)
    assert (
        local.guard is None and local.extra_body["chat_template_kwargs"]["enable_thinking"] is False
    )


def test_api_key_from_env_var_then_dotenv(tmp_path, monkeypatch):
    from training.policies import api_key

    dotenv = tmp_path / ".env"
    dotenv.write_text("# comment\nOTHER=x\nDEEPSEEK_API_KEY=from-dotenv\n")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert api_key("DEEPSEEK_API_KEY", dotenv) == "from-dotenv"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-env")
    assert api_key("DEEPSEEK_API_KEY", dotenv) == "from-env"
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    assert api_key("DEEPSEEK_API_KEY", tmp_path / "missing.env") == ""


def test_deepseek_config_disables_thinking(tmp_path, priced):
    # Verified 2026-11-15 against the live API: only this field removes reasoning tokens.
    from training.policies import policy_from_config

    p = policy_from_config(
        config.REPO_ROOT / "eval/configs/deepseek-v4-flash.toml",
        BudgetGuard(tmp_path / "l", 1, 1, "r"),
    )
    assert p.extra_body == {"thinking": {"type": "disabled"}}
