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
                "reference_runs": [{"args": ["-i", "{in:c}", "-c", "copy", "{out:out1}"]}] if i % 2 else None,
            }
            for i in range(n)
        }
        for sp in SPLITS
    }  # fmt: skip


def write_run(d, tasks, passes, reencode=False):
    d.mkdir(parents=True)
    ep_args = (
        ["-i", "{in:c}", "-c:v", "libx264", "{out:out1}"]
        if reencode
        else ["-i", "{in:c}", "-c", "copy", "{out:out1}"]
    )
    with (d / "results.jsonl").open("w") as r, (d / "episodes.jsonl").open("w") as e:
        for i, tid in enumerate(tasks):
            r.write(json.dumps({"task_id": tid, "success": passes(i), "runs": 1 + (i % 2)}) + "\n")
            e.write(
                json.dumps(
                    {
                        "task_id": tid,
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
    for system, (passes, reencode) in specs.items():
        runs[system] = {sp: tmp_path / system / sp for sp in SPLITS}
        for sp in SPLITS:
            write_run(tmp_path / system / sp, tasks[sp], passes, reencode)
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
    assert "Holm" in text and "Single training seed" in text and "by_family.csv" in text
    assert (
        res["systems"]["B2"]["test-iid"]["k"] == 0 and res["systems"]["M1"]["test-iid"]["n"] == 40
    )
    assert all(c["p_holm"] >= c["p_raw"] for c in res["comparisons"])
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
