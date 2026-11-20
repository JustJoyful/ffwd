import json

import pytest

from training import config
from training.env.loop import Episode
from training.grpo.telemetry import (
    TelemetryLog,
    grpo_reward,
    shuffle_within_groups,
    spec_accuracy,
    summarize,
)

GOLD = {
    "family": ["F1"],
    "outputs": [
        {
            "id": "out1",
            "kind": "video",
            "container": "mp4",
            "time": {"start_s": 2, "end_s": 5},
            "video": None,
        }
    ],
}


def task(**over):
    t = {
        "id": "t1",
        "split": "train",
        "gold_spec": GOLD,
        "families": ["F1"],
        "flags": {"ambiguous": False, "unsupported": False},
        "reference_runs": None,
    }
    return t | over


def check(ok_flags, re_encoded=False):
    checks = [
        {"field": f"f{i}", "expected": 1, "actual": 1 if ok else 0, "ok": ok}
        for i, ok in enumerate(ok_flags)
    ]
    return {
        "passed": all(ok_flags),
        "outputs": {
            "out1": {
                "passed": all(ok_flags),
                "checks": checks,
                "measurements": {"re_encoded": re_encoded},
                "error": None,
            }
        },
    }


def ep(**kw):
    base = {
        "task_id": "t1",
        "turns": [{"assistant": "x", "observation": {}}],
        "runs": 1,
        "invalid_turns": 0,
        "asked": False,
        "refused": False,
        "last_check": check([True]),
        "end_reason": "finish",
        "emitted_spec": None,
    }
    return Episode(**(base | kw))


def test_weights_come_from_config_and_match_the_architecture_table_except_spec_acc_which_is_0():
    # ARCHITECTURE 7.4 had spec_acc 0.2; D-043 (20 Nov 2026, before any GRPO run) set it to 0: the term is logged, not paid
    assert config.REWARD_WEIGHTS == {
        "pass": 1.0,
        "partial": 0.3,
        "spec_acc": 0.0,
        "efficiency": 0.1,
        "clarify": 0.5,
        "invalid": -0.5,
    }


def test_spec_acc_is_logged_but_does_not_change_the_reward():
    exact, empty = grpo_reward(task(), ep(emitted_spec=GOLD)), grpo_reward(task(), ep())
    assert exact.terms["spec_acc"] == 1.0 and empty.terms["spec_acc"] == 0.0
    assert exact.total == pytest.approx(empty.total)  # weight 0 (D-043): style no longer pays


def test_pass_gets_pass_and_efficiency_but_no_partial():
    r = grpo_reward(task(), ep())
    assert (
        r.terms["pass"] == 1 and r.terms["partial"] == 0 and r.terms["efficiency"] == 1
    )  # one run
    assert r.total == pytest.approx(1.0 + 0.1 * 1)


def test_partial_is_the_fraction_of_satisfied_fields_only_when_failing():
    r = grpo_reward(task(), ep(last_check=check([True, True, False, False])))
    assert r.terms["pass"] == 0 and r.terms["partial"] == pytest.approx(0.5)
    assert r.total == pytest.approx(0.3 * 0.5)


def test_efficiency_fewer_runs_and_no_needless_reencode():
    assert grpo_reward(task(), ep(runs=2)).terms["efficiency"] == pytest.approx(0.5)
    copy_ref = [
        {
            "action": "run",
            "args": ["-ss", "2", "-i", "{in:a}", "-c", "copy", "{out:out1}"],
            "inputs": ["a"],
            "outputs": ["out1"],
        }
    ]
    needless = grpo_reward(
        task(reference_runs=copy_ref), ep(last_check=check([True], re_encoded=True))
    )
    assert needless.terms["pass"] == 1 and needless.terms["efficiency"] == 0
    assert grpo_reward(task(reference_runs=copy_ref), ep()).terms["efficiency"] == 1


def test_clarify_rewards_correct_asks_and_refusals_and_penalises_over_asking():
    amb = task(flags={"ambiguous": True, "unsupported": False}, gold_spec=None)
    uns = task(flags={"ambiguous": False, "unsupported": True}, gold_spec=None)
    assert grpo_reward(amb, ep(asked=True, runs=0, last_check=None)).terms["clarify"] == 1
    assert grpo_reward(uns, ep(refused=True, runs=0, last_check=None)).terms["clarify"] == 1
    assert (
        grpo_reward(task(), ep(asked=True, runs=0, last_check=None)).terms["clarify"] == -1
    )  # over-asking
    assert (
        grpo_reward(task(), ep(refused=True, runs=0, last_check=None)).terms["clarify"] == -1
    )  # over-refusing
    assert grpo_reward(amb, ep(runs=1, last_check=None)).terms["clarify"] == 0


def test_invalid_actions_are_penalised_per_action_with_a_cap():
    r = grpo_reward(task(), ep(invalid_turns=2, last_check=check([False])))
    assert r.terms["invalid"] == 2 and r.total == pytest.approx(-1.0)
    assert (
        grpo_reward(task(), ep(invalid_turns=50, last_check=check([False]))).terms["invalid"]
        == config.REWARD_INVALID_CAP
    )


def test_spec_accuracy_is_field_level_f1_and_ignores_nulls():
    assert spec_accuracy(None, GOLD) == 0.0
    assert spec_accuracy(GOLD, GOLD) == 1.0
    half = {
        "family": ["F1"],
        "outputs": [
            {"id": "out1", "kind": "video", "container": "mkv", "time": {"start_s": 2, "end_s": 5}}
        ],
    }
    assert 0.5 < spec_accuracy(half, GOLD) < 1.0


def test_summarize_reports_no_signal_groups_and_the_breakdown():
    # group A: all four rollouts identical reward (no learning signal); group B: mixed
    recs = [
        dict(
            task_id="a",
            group="a",
            total=1.1,
            terms={
                "pass": 1,
                "partial": 0,
                "spec_acc": 0,
                "efficiency": 1,
                "clarify": 0,
                "invalid": 0,
            },
            invalid_turns=0,
            turns=2,
            supported=True,
            asked=False,
            refused=False,
            passed=True,
            runs=1,
        )
        for _ in range(4)
    ]
    recs += [
        dict(
            task_id="b",
            group="b",
            total=t,
            terms={
                "pass": p,
                "partial": 0,
                "spec_acc": 0,
                "efficiency": 0,
                "clarify": 0,
                "invalid": 1 if p == 0 else 0,
            },
            invalid_turns=1 if p == 0 else 0,
            turns=4,
            supported=True,
            asked=False,
            refused=p == 0,
            passed=bool(p),
            runs=1,
        )
        for t, p in [(1.0, 1), (-0.5, 0), (1.0, 1), (-0.5, 0)]
    ]
    row = summarize(recs, step=7)
    assert row["step"] == 7 and row["n_rollouts"] == 8 and row["n_groups"] == 2
    assert row["no_signal_group_share"] == 0.5
    assert row["mean_reward"] == pytest.approx((4.4 + 1.0 - 0.5 + 1.0 - 0.5) / 8)
    assert row["terms_mean"]["pass"] == pytest.approx(0.75) and set(row["terms_mean"]) == set(
        config.REWARD_WEIGHTS
    )
    assert row["invalid_action_rate"] == pytest.approx(
        2 / 24
    )  # 2 invalid turns over 4*2 + 4*4 total turns
    assert row["refusal_rate_on_supported"] == pytest.approx(2 / 8)
    assert row["pass_rate"] == pytest.approx(6 / 8)


def test_telemetry_log_appends_rows_and_spotchecks_top_rewards_every_n_steps(tmp_path):
    log = TelemetryLog(tmp_path / "telemetry.jsonl", tmp_path / "spotcheck", every=2, top_k=2)
    eps = [{"task_id": f"t{i}", "turns": []} for i in range(4)]
    recs = [
        dict(
            task_id=f"t{i}",
            group="g",
            total=float(i),
            terms={k: 0 for k in config.REWARD_WEIGHTS},
            invalid_turns=0,
            turns=1,
            supported=True,
            asked=False,
            refused=False,
            passed=False,
            runs=1,
        )
        for i in range(4)
    ]
    for step in (1, 2, 3, 4):
        log.add(step, recs, eps)
    rows = [json.loads(x) for x in (tmp_path / "telemetry.jsonl").read_text().splitlines()]
    assert [r["step"] for r in rows] == [1, 2, 3, 4]
    dumped = sorted(p.name for p in (tmp_path / "spotcheck").iterdir())
    assert dumped == ["step-2.jsonl", "step-4.jsonl"]
    top = [
        json.loads(x) for x in (tmp_path / "spotcheck" / "step-2.jsonl").read_text().splitlines()
    ]
    assert [t["episode"]["task_id"] for t in top] == ["t3", "t2"]  # highest rewards first


def test_shuffled_reward_control_permutes_within_groups_only():
    rewards = [1.0, 0.0, 0.0, 1.0, 5.0, 6.0]
    groups = ["a", "a", "b", "b", "c", "c"]
    out = shuffle_within_groups(rewards, groups, seed=1)
    for g in "abc":
        assert sorted(x for x, gg in zip(out, groups, strict=True) if gg == g) == sorted(
            x for x, gg in zip(rewards, groups, strict=True) if gg == g
        )
    assert shuffle_within_groups(rewards, groups, seed=1) == out  # deterministic
    assert any(shuffle_within_groups(rewards, groups, seed=s) != rewards for s in range(1, 6))


def test_summarize_handles_the_toy_reward_which_has_only_a_pass_term():
    # the default `--reward toy` path crashed on Kaggle with KeyError 'partial'
    rec = dict(
        task_id="a", group="a", total=1.0, terms={"pass": 1.0}, invalid_turns=0, turns=2,
        supported=True, asked=False, refused=False, passed=True, runs=1,
    )  # fmt: skip
    assert summarize([rec, rec], step=1)["terms_mean"] == {"pass": 1.0}
