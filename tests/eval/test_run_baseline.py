import json

import pytest

from eval.report import write_report
from eval.run_baseline import run_baseline
from training import config

TASKS = [
    json.loads(x) for x in (config.DATA_DIR / "tasks/dev/spike-v0.jsonl").read_text().splitlines()
]
SUBSET = [
    t for t in TASKS if t["id"] in ("s01-trim-first-3s", "u01-remove-person", "a01-make-shorter")
]
REFUSE = '{"action": "unsupported", "reason": "no"}'


def _run(tmp_path, policy, out="B2-fake", corpus=None, system="B2"):
    return run_baseline(
        system=system,
        policy=policy,
        tasks=SUBSET,
        out=tmp_path / out,
        corpus=corpus,
        meta={"model": "fake", "quant": "none", "temperature": 0.0},
        jobs_root=tmp_path / "jobs",
    )


def test_runner_refuses_existing_out(tmp_path, corpus):
    (tmp_path / "B2-fake").mkdir()
    with pytest.raises(FileExistsError):
        _run(tmp_path, lambda m: REFUSE, corpus=corpus)


def test_runner_records_episode_exception_as_failure(tmp_path, corpus):
    def broken(messages):
        raise RuntimeError("server down")

    out = _run(tmp_path, broken, corpus=corpus)
    lines = [json.loads(x) for x in (out / "results.jsonl").read_text().splitlines()]
    assert len(lines) == len(SUBSET)
    assert all(r["success"] is False and r["end_reason"] == "error" for r in lines)
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["n_tasks"] == len(SUBSET) and manifest["system"] == "B2"
    assert len(manifest["tasks_sha256"]) == 64 and manifest["git_commit"]


def test_runner_scores_and_report(tmp_path, corpus):
    out = _run(tmp_path, lambda m: REFUSE, corpus=corpus)
    by_id = {
        r["task_id"]: r for r in map(json.loads, (out / "results.jsonl").read_text().splitlines())
    }
    assert by_id["u01-remove-person"]["success"] is True
    assert by_id["s01-trim-first-3s"]["success"] is False
    assert by_id["a01-make-shorter"]["success"] is False
    other = _run(tmp_path, lambda m: REFUSE, out="X1-fake", corpus=corpus, system="X1")
    md = tmp_path / "report.md"
    write_report(md, [out, other])
    text = md.read_text()
    assert "B2-fake" in text and "X1-fake" in text and "X1-fake − B2-fake" in text
    with pytest.raises(FileExistsError):
        write_report(md, [out])
