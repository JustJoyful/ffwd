from eval.g3_criteria import criterion_a


def _t(total, kept):
    return {"summary": {"total": total, "kept": kept}}


def test_pass_needs_both_the_share_and_the_task_count_at_the_stated_full_scale():
    r = criterion_a([_t(300, 90), _t(300, 90)])  # 30% -> 900 of 3000
    assert (
        r["verdict"] == "pass"
        and r["share_ok"]
        and r["tasks_ok"]
        and r["estimated_in_band_tasks"] == 900
    )


def test_share_just_under_25_percent_fails():
    r = criterion_a([_t(300, 70), _t(300, 70)])  # 23.3%
    assert r["verdict"] == "fail" and not r["share_ok"]


def test_a_count_that_depends_on_the_unfixed_full_scale_is_unclear_not_pass():
    # 13.5% would fail the share rule; use a share that passes it but whose count passes only at 4000:
    r = criterion_a([_t(600, 150)], full_scale=1500)  # 25% x 1500 = 375 < 400, x 4000 = 1000
    assert r["verdict"] == "unclear" and r["share_ok"] and not r["tasks_ok"]


def test_the_two_pilots_are_pooled_not_averaged():
    r = criterion_a([_t(100, 50), _t(900, 100)])  # pooled 15%, not the mean of 50% and 11%
    assert r["pilot_tasks"] == 1000 and r["in_band"] == 150 and abs(r["share"] - 0.15) < 1e-9
