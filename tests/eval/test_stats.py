import pytest
from scipy.stats import binomtest

from eval.stats import paired_diff_ci, wilson_ci


@pytest.mark.parametrize("k,n", [(0, 50), (50, 50), (4, 50), (47, 50), (1, 44), (3, 3)])
def test_wilson_matches_scipy_reference(k, n):
    # Independent implementation (scipy) computes the expected interval; nothing is hard-coded.
    ref = binomtest(k, n).proportion_ci(confidence_level=0.95, method="wilson")
    p, lo, hi = wilson_ci(k, n)
    assert p == pytest.approx(k / n)
    assert lo == pytest.approx(ref.low, abs=1e-9) and hi == pytest.approx(ref.high, abs=1e-9)


def test_wilson_zero_successes_is_not_a_degenerate_interval():
    # The percentile bootstrap returned [0%, 0%] for 0/50; the true uncertainty is about [0%, 7%].
    p, lo, hi = wilson_ci(0, 50)
    assert (p, lo) == (0.0, 0.0) and 0.05 < hi < 0.09
    p, lo, hi = wilson_ci(50, 50)
    assert (p, hi) == (1.0, 1.0) and 0.91 < lo < 0.95


def test_wilson_rejects_bad_counts():
    for k, n in ((1, 0), (-1, 5), (6, 5)):
        with pytest.raises(ValueError):
            wilson_ci(k, n)


def test_paired_diff():
    a = {f"t{i}": True for i in range(30)}
    b = {f"t{i}": i < 15 for i in range(30)}
    mean, low, high = paired_diff_ci(a, b)
    assert mean == pytest.approx(0.5) and 0.3 < low < mean < high <= 0.7


def test_paired_diff_rejects_mismatched_ids():
    with pytest.raises(ValueError):
        paired_diff_ci({"a": True, "b": False}, {"a": True})
