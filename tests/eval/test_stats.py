import pytest

from eval.stats import bootstrap_ci, paired_diff_ci


def test_bootstrap_all_true():
    assert bootstrap_ci([True] * 20) == (1.0, 1.0, 1.0)


def test_bootstrap_half_brackets_half():
    mean, low, high = bootstrap_ci([i % 2 == 0 for i in range(100)])
    assert mean == 0.5 and low < 0.5 < high and high - low < 0.25


def test_bootstrap_is_deterministic():
    xs = [i % 3 == 0 for i in range(50)]
    assert bootstrap_ci(xs) == bootstrap_ci(xs)


def test_paired_diff():
    a = {f"t{i}": True for i in range(30)}
    b = {f"t{i}": i < 15 for i in range(30)}
    mean, low, high = paired_diff_ci(a, b)
    assert mean == pytest.approx(0.5) and 0.3 < low < mean < high <= 0.7


def test_paired_diff_rejects_mismatched_ids():
    with pytest.raises(ValueError):
        paired_diff_ci({"a": True, "b": False}, {"a": True})
