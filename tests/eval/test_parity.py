import pytest

from eval.parity import mcnemar_exact, parity


def test_identical_results_agree_fully():
    r = {f"t{i}": i % 3 == 0 for i in range(30)}
    out = parity(r, dict(r))
    assert (
        out["agreement"] == 1.0
        and out["only_a_passes"] == out["only_b_passes"] == 0
        and out["mcnemar_p"] == 1.0
    )
    assert out["b_minus_a"]["diff"] == 0.0


def test_discordant_pairs_are_counted_and_the_diff_has_the_right_sign():
    a = {"x": True, "y": True, "z": False, "w": False}
    b = {"x": True, "y": False, "z": True, "w": True}
    out = parity(a, b)
    assert (out["only_a_passes"], out["only_b_passes"]) == (1, 2) and out["agreement"] == 0.25
    assert out["b_minus_a"]["diff"] == pytest.approx(0.25)


def test_mcnemar_exact_known_values():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 5) == 1.0
    assert mcnemar_exact(0, 10) == pytest.approx(2 / 1024)  # two-sided exact binomial


def test_task_sets_must_match():
    with pytest.raises(ValueError):
        parity({"a": True}, {"b": True})
