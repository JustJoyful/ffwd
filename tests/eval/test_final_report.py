import json

import pytest

from eval.final_report import final_report, last_run_args, reencode_rate
from eval.stats import holm, paired_diff_pvalue

SPLITS = ("test-iid", "test-phrasing")


def make_tasks(n=40):
    return {
        sp: {
            f"{sp}-{i}": {
                "families": ["F1"] if i % 2 else ["F4", "F6"], "difficulty": 1 if i % 2 else 2,
                "flags": {"ambiguous": False, "unsupported": False},
                "reference_runs": [{"args": ["-i", "{in:c}", "-c", "copy", "{out:out1}"] if i % 2 else ["-i", "{in:c}", "-c:v", "libx264", "{out:out1}"]}],
            }
            for i in range(n)
        }
        for sp in SPLITS
    }  # fmt: skip


def write_run(d, tasks, passes, reencode=False, runs=lambda i: 1 + (i % 2)):
    d.mkdir(parents=True)
    ep_args = (
        ["-i", "{in:c}", "-c:v", "libx264", "{out:out1}"]
        if reencode
        else ["-i", "{in:c}", "-c", "copy", "{out:out1}"]
    )
    with (d / "results.jsonl").open("w") as r, (d / "episodes.jsonl").open("w") as e:
        for i, tid in enumerate(tasks):
            r.write(json.dumps({"task_id": tid, "success": passes(i), "runs": runs(i)}) + "\n")
            e.write(
                json.dumps(
                    {
                        "task_id": tid,
                        "last_check": {
                            "passed": True,
                            "outputs": {"out1": {"measurements": {"re_encoded": reencode}}},
                        },
                        "turns": [
                            {
                                "assistant": json.dumps({"action": "run", "args": ep_args}),
                                "observation": {},
                            }
                        ],
                    }
                )
                + "\n"
            )


def runs_for(tmp_path, tasks, specs):
    runs = {}
    for system, (passes, reencode, *rest) in specs.items():
        runs[system] = {sp: tmp_path / system / sp for sp in SPLITS}
        for sp in SPLITS:
            write_run(tmp_path / system / sp, tasks[sp], passes, reencode, *rest)
    return runs


def test_report_has_cis_holm_and_by_family(tmp_path):
    tasks = make_tasks()
    runs = runs_for(
        tmp_path, tasks, {"M1": (lambda i: i % 4 != 0, False), "B2": (lambda i: False, True)}
    )
    out = final_report(
        runs,
        tasks,
        [("Q2: M1 vs B2", "B2", "M1", "test-iid"), ("Q5", "B2", "M1", "test-phrasing")],
        tmp_path / "rep",
    )
    text = (out / "summary.md").read_text()
    res = json.loads((out / "results.json").read_text())
    assert "fixed-sequence" in text and "Single training seed" in text and "by_family.csv" in text
    assert (
        res["systems"]["B2"]["test-iid"]["k"] == 0 and res["systems"]["M1"]["test-iid"]["n"] == 40
    )
    assert [c["status"] for c in res["comparisons"]][0] == "rejected"
    assert (
        res["systems"]["M1"]["reencode_rate_iid"] == 0.0
        and res["systems"]["B2"]["reencode_rate_iid"] == 1.0
    )
    assert "family:F4+F6" in (out / "by_family.csv").read_text()


def test_mismatched_denominators_are_refused(tmp_path):
    tasks = make_tasks()
    runs = runs_for(tmp_path, tasks, {"M1": (lambda i: True, False), "B2": (lambda i: True, False)})
    victim = runs["B2"]["test-iid"] / "results.jsonl"
    victim.write_text("".join(victim.read_text().splitlines(keepends=True)[:-1]))  # B2 lost a task
    with pytest.raises(ValueError, match="different task sets"):
        final_report(runs, tasks, [], tmp_path / "rep")


def test_failed_runs_stay_in_the_denominator(tmp_path):
    tasks = make_tasks()
    runs = runs_for(tmp_path, tasks, {"M1": (lambda i: i < 10, False)})
    res = json.loads((final_report(runs, tasks, [], tmp_path / "rep") / "results.json").read_text())
    assert (res["systems"]["M1"]["test-iid"]["k"], res["systems"]["M1"]["test-iid"]["n"]) == (
        10,
        40,
    )


def test_missing_test_lock_is_refused_and_existing_output_is_never_overwritten(tmp_path):
    tasks = make_tasks()
    runs = runs_for(tmp_path, tasks, {"M1": (lambda i: True, False)})
    ledger = tmp_path / "runs.jsonl"
    ledger.write_text(json.dumps({"system": "M1", "checkpoint": "s90", "split": "test-iid"}) + "\n")
    with pytest.raises(ValueError, match="no test-run lock"):
        final_report(runs, tasks, [], tmp_path / "rep", ledger=ledger, checkpoints={"M1": "s90"})
    out = final_report(runs, tasks, [], tmp_path / "ok")
    with pytest.raises(FileExistsError):
        final_report(runs, tasks, [], out)


def test_holm_and_bootstrap_p_behave():
    assert holm({"a": 0.01, "b": 0.04, "c": 0.5}) == {"a": 0.03, "b": 0.08, "c": 0.5}
    a = {str(i): True for i in range(60)}
    b = {str(i): i % 2 == 0 for i in range(60)}
    assert paired_diff_pvalue(a, b) < 0.01 and paired_diff_pvalue(a, dict(a)) == 1.0


def test_last_run_args_and_reencode_rate_edge_cases():
    assert last_run_args({"turns": [{"assistant": "not json"}]}) is None
    assert reencode_rate({}, {}, {"t": {"reference_runs": None}}) is None


def test_preregistered_sequence_is_the_amended_order():
    from training import config

    fam = config.PREREG_COMPARISONS
    assert [c[0].split()[0] for c in fam] == ["Q2", "Q7", "Q3a", "Q3b", "Q4"]
    by = {c[0].split()[0]: c for c in fam}
    assert by["Q7"][1:4] == (
        "B0",
        "M3",
        "test-phrasing",
    )  # test-real left the Phase 1 family (Amendment 3)
    assert by["Q3a"][3] == "test-iid+test-phrasing" and by["Q3a"][5] is True
    assert by["Q3b"][4:] == ("runs", True) and by["Q4"][1:4] == ("X1", "M3", "test-iid")
    assert config.PREREG_PROCEDURE == "fixed-sequence" and config.PREREG_ALPHA == 0.05
    assert config.PREREG_GUARD == ("M1", "M3", ("test-iid", "test-compositional", "test-phrasing"))
    assert config.PREREG_GUARD_MARGIN == 0.02


def test_prereg_text_names_the_same_order_as_the_config():
    from training import config

    text = (config.REPO_ROOT / "eval" / "PREREGISTRATION.md").read_text()
    order = " -> ".join(c[0].split()[0] for c in config.PREREG_COMPARISONS)
    assert order in text, "eval/PREREGISTRATION.md must state the testing order the code uses"


def test_pooled_comparison_is_one_entry_plus_descriptive_rows(tmp_path):
    tasks = make_tasks()
    runs = runs_for(
        tmp_path, tasks, {"M3": (lambda i: i % 4 != 0, False), "B0": (lambda i: i % 2 == 0, False)}
    )
    out = final_report(
        runs, tasks, [("Q7 pooled", "B0", "M3", "test-iid+test-phrasing")], tmp_path / "rep"
    )
    res = json.loads((out / "results.json").read_text())
    assert (
        len(res["comparisons"]) == 1 and res["comparisons"][0]["split"] == "test-iid+test-phrasing"
    )
    assert {c["split"] for c in res["descriptive"]} == {"test-iid", "test-phrasing"}
    assert "Descriptive only" in (out / "summary.md").read_text()


def test_dedup_subset_is_a_second_iid_column_with_descriptive_diffs(tmp_path):
    tasks = make_tasks()
    runs = runs_for(
        tmp_path, tasks, {"M1": (lambda i: i % 4 != 0, False), "B2": (lambda i: False, True)}
    )
    dedup = frozenset(list(tasks["test-iid"])[:30])
    out = final_report(
        runs, tasks, [("Q2", "B2", "M1", "test-iid")], tmp_path / "rep", iid_dedup_ids=dedup
    )
    text = (out / "summary.md").read_text()
    res = json.loads((out / "results.json").read_text())
    assert "test-iid (dedup)" in text.splitlines()[4]  # header row
    assert res["systems"]["M1"]["test-iid (dedup)"]["n"] == 30
    assert res["systems"]["M1"]["test-iid"]["n"] == 40  # the full split is still reported
    assert [c["split"] for c in res["comparisons"]] == ["test-iid"]  # Holm family untouched
    assert [d["split"] for d in res["descriptive"]] == ["test-iid (dedup)"]
    with pytest.raises(ValueError, match="not in test-iid"):
        final_report(runs, tasks, [], tmp_path / "rep2", iid_dedup_ids=frozenset({"nope"}))


def seq(tmp_path, tasks, specs, comps, **kw):
    runs = runs_for(tmp_path, tasks, specs)
    out = final_report(runs, tasks, comps, tmp_path / "rep", **kw)
    return json.loads((out / "results.json").read_text()), (out / "summary.md").read_text()


def test_sequence_stops_at_the_first_non_rejection_and_later_steps_are_descriptive(tmp_path):
    tasks = make_tasks()
    comps = [
        ("A", "B2", "M1", "test-iid"),  # M1 far better than B2: rejected
        ("B", "M1", "M1x", "test-iid"),  # identical systems: p = 1, not rejected, stops here
        ("C", "B2", "M1", "test-phrasing"),  # would be significant, but is after the stop
    ]
    res, text = seq(
        tmp_path,
        tasks,
        {
            "B2": (lambda i: False, False),
            "M1": (lambda i: True, False),
            "M1x": (lambda i: True, False),
        },
        comps,
    )
    got = {c["name"]: c for c in res["comparisons"]}
    assert got["A"]["status"] == "rejected" and got["A"]["p_raw"] < 0.05
    assert got["B"]["status"].startswith("NOT rejected")
    assert got["C"]["status"].startswith("descriptive") and got["C"]["p_raw"] is None
    assert "descriptive (after the stop)" in text


def test_a_significant_difference_in_the_unfavourable_direction_stops_the_sequence(tmp_path):
    tasks = make_tasks()
    comps = [
        ("W", "M1", "B2", "test-iid"),
        ("X", "B2", "M1", "test-iid"),
    ]  # B2 - M1: significantly negative
    res, _ = seq(
        tmp_path, tasks, {"B2": (lambda i: False, False), "M1": (lambda i: True, False)}, comps
    )
    assert res["comparisons"][0]["p_raw"] < 0.05 and not res["comparisons"][0]["favourable"]
    assert res["comparisons"][0]["status"].startswith("significant, UNFAVOURABLE")
    assert res["comparisons"][1]["status"].startswith("descriptive")


def test_q3b_counts_runs_on_graded_tasks_only_and_failed_runs_count_what_they_used(tmp_path):
    tasks = make_tasks()
    tasks["test-iid"]["test-iid-0"]["flags"][
        "unsupported"
    ] = True  # not graded: leaves the denominator
    comps = [("Q3b", "M1", "M3", "test-iid", "runs", True)]
    res, _ = seq(
        tmp_path,
        tasks,
        {
            "M1": (lambda i: True, False, lambda i: 2),
            "M3": (lambda i: i % 5, False, lambda i: 1 if i % 5 else 0),
        },
        comps,
    )
    c = res["comparisons"][0]
    assert c["n"] == 39 and c["diff_b_minus_a"] < 0 and c["favourable"]  # 1 or 0 runs against 2


def test_q3a_needless_or_fail_counts_failures_no_runs_and_re_encodes_on_copy_eligible_only(
    tmp_path,
):
    from eval.final_report import needless_or_fail

    assert needless_or_fail({"task_id": "t", "success": False, "runs": 3}, None) == 1.0  # failed
    assert (
        needless_or_fail({"task_id": "t", "success": True, "runs": 0}, None) == 1.0
    )  # ran nothing

    def ep(re):
        return {"last_check": {"outputs": {"o": {"measurements": {"re_encoded": re}}}}}

    assert needless_or_fail({"task_id": "t", "success": True, "runs": 1}, ep(True)) == 1.0
    assert needless_or_fail({"task_id": "t", "success": True, "runs": 1}, ep(False)) == 0.0
    with pytest.raises(ValueError, match="no last_check"):
        needless_or_fail({"task_id": "t", "success": True, "runs": 1}, {})
    tasks = make_tasks()  # odd indices have a stream-copy reference run: 20 per split, 40 pooled
    comps = [("Q3a", "M1", "M3", "test-iid+test-phrasing", "needless_or_fail", True)]
    res, _ = seq(
        tmp_path, tasks, {"M1": (lambda i: True, True), "M3": (lambda i: True, False)}, comps
    )
    c = res["comparisons"][0]
    assert c["n"] == 40 and c["diff_b_minus_a"] == -1.0 and c["status"] == "rejected"
    assert {d["split"] for d in res["descriptive"]} == {"test-iid", "test-phrasing"}


def test_guard_and_the_efficiency_claim(tmp_path):
    def three_splits(tmp, m3_pass):
        t = make_tasks()
        t["test-compositional"] = {
            k.replace("test-phrasing", "test-compositional"): v
            for k, v in t["test-phrasing"].items()
        }
        runs = {}
        for system, (passes, rerun) in {
            "M1": (lambda i: True, True),
            "M3": (m3_pass, False),
        }.items():
            runs[system] = {}
            for sp in ("test-iid", "test-compositional", "test-phrasing"):
                runs[system][sp] = tmp / system / sp
                write_run(runs[system][sp], t[sp], passes, rerun)
        comps = [("Q3a", "M1", "M3", "test-iid+test-phrasing", "needless_or_fail", True)]
        out = final_report(runs, t, comps, tmp / "rep")
        return json.loads((out / "results.json").read_text())

    ok = three_splits(tmp_path / "a", lambda i: True)  # M3 as successful as M1 and never re-encodes
    assert ok["guard"]["met"] and ok["efficiency_claim"]
    bad = three_splits(tmp_path / "b", lambda i: i % 10 != 0)  # M3 loses 10% of tasks
    assert not bad["guard"]["met"] and not bad["efficiency_claim"]
    assert (
        bad["comparisons"][0]["status"] == "rejected"
    )  # Q3a rejects, yet no efficiency claim without the guard


def test_a_metric_with_no_tasks_stops_the_sequence_instead_of_crashing(tmp_path):
    tasks = make_tasks()
    for sp in tasks:  # nothing is copy-eligible: Q3a has no tasks (a short partial or dry run)
        for t in tasks[sp].values():
            t["reference_runs"] = [{"args": ["-i", "{in:c}", "-c:v", "libx264", "{out:out1}"]}]
    comps = [("Q3a", "M1", "M3", "test-iid+test-phrasing", "needless_or_fail", True), ("Q3b", "M1", "M3", "test-iid", "runs", True)]  # fmt: skip
    res, text = seq(
        tmp_path, tasks, {"M1": (lambda i: True, False), "M3": (lambda i: True, False)}, comps
    )
    assert res["comparisons"][0]["n"] == 0 and "NOT computable" in res["comparisons"][0]["status"]
    assert res["comparisons"][1]["status"].startswith("descriptive") and "NOT computable" in text
