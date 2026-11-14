import pytest

from training import config
from training.teacher import budget
from training.teacher.budget import (
    BudgetConfigError,
    BudgetExceeded,
    BudgetGuard,
    cost_from_usage,
    require_pricing,
    worst_case_cost,
)

PRICES = {"input_cache_hit": 0.006, "input_cache_miss": 0.3, "output": 1.2}


def _guard(tmp_path, lifetime=1.0, run_cap=0.5, run_id="r1"):
    return BudgetGuard(tmp_path / "ledger.jsonl", lifetime, run_cap, run_id)


def test_reserve_blocks_over_lifetime_cap(tmp_path):
    g = _guard(tmp_path, lifetime=1.0, run_cap=10)
    g.reserve(0.6)
    with pytest.raises(BudgetExceeded):
        g.reserve(0.5)


def test_reserve_blocks_over_run_cap(tmp_path):
    g = _guard(tmp_path, lifetime=10, run_cap=0.25)
    g.reserve(0.2)
    with pytest.raises(BudgetExceeded):
        g.reserve(0.1)


def test_lifetime_cap_spans_runs(tmp_path):
    _guard(tmp_path, run_cap=10, run_id="old").reserve(0.9)
    with pytest.raises(BudgetExceeded):
        _guard(tmp_path, run_id="new").reserve(0.2)


def test_unsettled_reservation_still_counts(tmp_path):
    _guard(tmp_path).reserve(0.4)  # process "dies" before settle
    assert _guard(tmp_path).spent() == pytest.approx(0.4)


def test_settle_replaces_reservation_with_actual(tmp_path):
    g = _guard(tmp_path)
    rid = g.reserve(0.4)
    g.settle(
        rid,
        {"prompt_cache_hit_tokens": 10, "prompt_cache_miss_tokens": 5, "completion_tokens": 3},
        0.01,
    )
    assert g.spent() == pytest.approx(0.01) and g.spent(run_only=True) == pytest.approx(0.01)


def test_cache_hit_ratio(tmp_path):
    g = _guard(tmp_path)
    for hit, miss in ((900, 100), (500, 500)):
        g.settle(
            g.reserve(0.01), {"prompt_cache_hit_tokens": hit, "prompt_cache_miss_tokens": miss}, 0.0
        )
    assert g.cache_hit_ratio() == pytest.approx(1400 / 2000)


def test_costs():
    usage = {
        "prompt_cache_hit_tokens": 1_000_000,
        "prompt_cache_miss_tokens": 1_000_000,
        "completion_tokens": 1_000_000,
    }
    assert cost_from_usage(usage, PRICES) == pytest.approx(0.006 + 0.3 + 1.2)
    assert cost_from_usage(
        {"prompt_tokens": 1_000_000, "completion_tokens": 0}, PRICES
    ) == pytest.approx(0.3)
    assert worst_case_cost(1_000_000, 1_000_000, PRICES) == pytest.approx(1.5)


def test_unset_prices_raise_config_error(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_MODEL_ID", None)
    with pytest.raises(BudgetConfigError):
        require_pricing()


def test_pricing_uses_peak_rates():
    assert budget.billing_prices() == config.DEEPSEEK_PRICES_USD_PER_MTOK["peak"]
