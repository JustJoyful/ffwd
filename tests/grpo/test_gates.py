from training.grpo.gates import StopRules


def row(no_signal=0.1, refusal=0.0, invalid=0.05):
    return {
        "no_signal_group_share": no_signal,
        "refusal_rate_on_supported": refusal,
        "invalid_action_rate": invalid,
    }


def test_healthy_run_never_stops():
    g = StopRules()
    assert all(g.update(row()) == [] for _ in range(50))


def test_no_signal_needs_ten_consecutive_steps_and_resets_on_recovery():
    g = StopRules()
    for _ in range(9):
        assert g.update(row(no_signal=0.9)) == []
    assert g.update(row(no_signal=0.9)) == ["no_signal_groups"]
    g = StopRules()
    for _ in range(9):
        g.update(row(no_signal=0.9))
    g.update(row(no_signal=0.1))  # recovery resets the streak
    assert g.update(row(no_signal=0.9)) == []


def test_refusal_collapse_stops_after_three_steps():
    g = StopRules()
    assert g.update(row(refusal=0.5)) == [] and g.update(row(refusal=0.5)) == []
    assert g.update(row(refusal=0.5)) == ["refusal_collapse"]


def test_rising_invalid_rate_for_ten_steps_stops():
    g, out = StopRules(), []
    for i in range(12):
        out.append(g.update(row(invalid=0.05 + 0.01 * i)))
    assert out[10] == ["invalid_actions_rising"] and all(o == [] for o in out[:10])
