import pytest

from eval.grpo_checkpoint_dev import judge


def rows(successes, invalid=0):
    out = [
        {"task_id": f"t{i}", "success": ok, "invalid_turns": 0} for i, ok in enumerate(successes)
    ]
    for r in out[:invalid]:
        r["invalid_turns"] = 1
    return out


M1 = rows([True] * 293 + [False] * 7)
METRICS = [
    {"step": 1, "gpu_hours": 0.027},
    {"step": 2, "gpu_hours": 0.008},
    {"step": 3, "gpu_hours": 0.010},
]


def test_control_equal_to_m1_passes_and_reports_gpu_hours_per_step():
    j = judge(rows([True] * 293 + [False] * 7), M1, METRICS)
    assert j["control_passes"] and j["not_above_m1_ci"] and j["format_ok"]
    g = j["gpu_hours_per_step"]
    assert g["steps"] == 3 and g["mean_without_step1"] == pytest.approx(0.009)
    assert g["projected_60_steps"] == pytest.approx(60 * 0.009)  # step 1 (warm-up) is left out


def test_a_control_that_improves_beyond_the_m1_interval_fails():
    j = judge(rows([True] * 300), M1, METRICS)  # 100% is above M1's upper Wilson bound (about 99%)
    assert not j["not_above_m1_ci"] and not j["control_passes"]


def test_a_worse_control_passes_the_not_above_rule_and_invalid_actions_fail_the_format_rule():
    worse = judge(rows([True] * 280 + [False] * 20), M1, METRICS)
    assert worse["not_above_m1_ci"] and worse["control_passes"]
    broken = judge(rows([True] * 293 + [False] * 7, invalid=20), M1, METRICS)  # 6.7% of episodes
    assert not broken["format_ok"] and not broken["control_passes"]


def test_different_task_sets_are_refused():
    with pytest.raises(ValueError, match="different dev tasks"):
        judge(rows([True] * 299), M1, METRICS)
