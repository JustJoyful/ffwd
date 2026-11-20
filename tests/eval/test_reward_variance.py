from eval.reward_variance import analyse, group_causes
from training import config

W = config.REWARD_WEIGHTS
OLD = W | {"spec_acc": 0.2}  # the pre-D-043 weights: the term the 20 Nov analysis was about


def rec(tid, *, passed=True, runs=1, reenc=False, spec=1.0, partial=0.0, supported=True):
    terms = {
        "pass": 1.0 if passed else 0.0,
        "partial": 0.0 if passed else partial,
        "spec_acc": spec,
        "efficiency": 0.0 if (not passed or reenc) else 1.0 / runs,
        "clarify": 0.0,
        "invalid": 0.0,
    }
    return {
        "task_id": tid,
        "total": sum(W[k] * v for k, v in terms.items()),
        "terms": terms,
        "runs": runs,
        "passed": passed,
        "needless_reencode": reenc,
        "supported": supported,
    }


def test_identical_samples_have_no_signal():
    c = group_causes([rec("a")] * 8)
    assert not c["signal"] and c["varying"] == [] and c["primary"] is None


def test_all_pass_but_one_run_more_is_runs_signal_only():
    c = group_causes([rec("a")] * 7 + [rec("a", runs=2)])
    assert c["signal"] and not c["pass_varies"]
    assert c["only"] == "efficiency" and c["efficiency_sources"] == ["runs"]


def test_needless_reencode_is_its_own_source():
    c = group_causes([rec("a")] * 7 + [rec("a", reenc=True)])
    assert c["signal"] and not c["pass_varies"] and c["efficiency_sources"] == ["re_encode"]


def test_spec_accuracy_alone_can_create_signal():
    c = group_causes([rec("a")] * 7 + [rec("a", spec=0.5)], OLD)
    assert c["signal"] and c["only"] == "spec_acc"


def test_failures_with_different_partial_credit_vary_in_partial():
    c = group_causes([rec("a", passed=False, partial=0.2), rec("a", passed=False, partial=0.8)])
    assert c["signal"] and not c["pass_varies"] and c["only"] == "partial"


def test_pass_difference_is_primary_and_not_counted_as_efficiency_cause():
    c = group_causes([rec("a")] * 4 + [rec("a", passed=False)] * 4)
    assert c["pass_varies"] and c["primary"] == "pass"
    assert c["efficiency_sources"] == ["pass_differs"]


def test_zero_spec_acc_weight_removes_spec_only_signal_but_keeps_the_rest():
    spec_only = [rec("a")] * 7 + [rec("a", spec=0.5)]
    runs = [rec("b")] * 7 + [rec("b", runs=2)]
    w0 = OLD | {"spec_acc": 0.0}
    assert group_causes(spec_only, OLD)["signal"] and not group_causes(spec_only, w0)["signal"]
    assert group_causes(runs, w0)["signal"]
    out = analyse(spec_only + runs, w0)
    assert out["signal_total_reward"]["n"] == 1
    assert "spec_acc" not in out["pass_constant_groups_signal_terms"]


def test_pool_has_tasks_with_nonzero_reward_variance_without_spec_acc_and_counts_unique_contents():
    from eval.reward_variance import build_pool

    recs = (
        [rec("same")] * 8  # no variance
        + [rec("style")] * 7
        + [rec("style", spec=0.5)]  # spec_acc only: not in the pool at weight 0
        + [rec("runs")] * 7
        + [rec("runs", runs=2)]  # efficiency/runs: in the pool
        + [rec("runs2")] * 6
        + [rec("runs2", runs=3)] * 2  # same content as "runs", also in
        + [rec("flip")] * 4
        + [rec("flip", passed=False)] * 4  # pass variance: in
    )
    keys = {"same": "k1", "style": "k2", "runs": "k3", "runs2": "k3", "flip": "k4"}
    cats = {"runs": ["copy"], "runs2": ["copy", "speed"], "same": ["copy"], "flip": ["speed"]}
    ids, s = build_pool(recs, keys, cats)
    assert ids == ["runs", "runs2", "flip"] and s["pool_tasks"] == 3 and s["groups_sampled"] == 5
    assert s["pool_unique_contents"] == 2 and s["sampled_unique_contents"] == 4
    assert "spec_acc" not in s["varying_term_in_pool"] and s["pass_varies_in_pool"] == 1
    assert s["by_category"]["copy"] == {"sampled": 3, "in_pool": 2, "share": 2 / 3}
    ids_old, _ = build_pool(recs, keys, cats, OLD)
    assert "style" in ids_old  # under the old weights the style-only group counted


def test_analyse_counts_groups_not_samples():
    recs = [rec("a")] * 8 + [rec("b")] * 7 + [rec("b", runs=2)] + [rec("c", passed=False)] * 8
    out = analyse(recs)
    assert out["groups"] == 3 and out["signal_total_reward"]["n"] == 1
    assert out["signal_without_pass_variance"]["n"] == 1 and out["signal_pass_only_view"]["n"] == 0
    assert out["efficiency_sources"] == {"runs": 1}
