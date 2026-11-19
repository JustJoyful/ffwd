import json

from eval.recovery_eval import first_run_failed, natural_recovery


def _run(obs):
    return {"assistant": json.dumps({"action": "run", "args": ["-i", "x"]}), "observation": obs}


PASS = {"run_ok": True, "checks": {"out1": {"passed": True}}}
FAIL = {"run_ok": True, "checks": {"out1": {"passed": False}}}


def test_first_run_failed_reads_the_first_run_only():
    spec = {
        "assistant": json.dumps({"action": "spec", "spec": {}}),
        "observation": {"spec": "confirmed"},
    }
    assert first_run_failed({"turns": [spec, _run(FAIL), _run(PASS)]}) is True
    assert first_run_failed({"turns": [spec, _run(PASS)]}) is False
    assert (
        first_run_failed({"turns": [spec, _run({"run_ok": False, "rejected": "bad flag"})]}) is True
    )
    assert first_run_failed({"turns": [spec, _run({"error": "x"})]}) is True  # never ran
    assert first_run_failed({"turns": [spec]}) is None
    assert first_run_failed({"turns": [{"assistant": "not json", "observation": {}}]}) is None


def test_natural_recovery_counts_only_tasks_with_a_failed_first_run(tmp_path):
    eps = [[_run(PASS)], [_run(FAIL), _run(PASS)], [_run(FAIL), _run(FAIL)], []]
    ok = [True, True, False, True]
    (tmp_path / "results.jsonl").write_text(
        "".join(json.dumps({"task_id": f"t{i}", "success": s}) + "\n" for i, s in enumerate(ok))
    )
    (tmp_path / "episodes.jsonl").write_text(
        "".join(json.dumps({"task_id": f"t{i}", "turns": t}) + "\n" for i, t in enumerate(eps))
    )
    r = natural_recovery(tmp_path)
    assert (r["tasks_with_a_failed_first_run"], r["recovered"], r["of_tasks"]) == (2, 1, 4)
    assert abs(r["rate"] - 0.5) < 1e-9 and r["ci95"][0] < 0.5 < r["ci95"][1]
