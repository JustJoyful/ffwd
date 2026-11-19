from training.taskgen.loader import load_tasks
from training.teacher.run import pilot_selection


def test_pilot_selection_is_fixed_stratified_and_at_most_20():
    tasks = load_tasks("train", purpose="teacher")
    a, b = pilot_selection(tasks), pilot_selection(tasks)
    assert (
        [t["id"] for t in a] == [t["id"] for t in b]
        and len(a) <= 20
        and {t["split"] for t in a} == {"train"}
    )
    singles = {
        t["families"][0] for t in a if len(t["families"]) == 1 and not t["flags"]["ambiguous"]
    }
    assert {f"F{k}" for k in range(1, 13)} <= singles  # every family, incl. F11
    assert any(t["flags"]["ambiguous"] for t in a) and any(t["flags"]["unsupported"] for t in a)


# --- bulk loop (chunks, gate, peak sleep) with a fake teacher --------------------------------------------------
import json  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

from fakes import TRIM, ReferenceTeacher  # noqa: E402

from training.teacher import run as run_mod  # noqa: E402
from training.teacher.budget import BudgetGuard  # noqa: E402


def _tasks(n):
    return [
        dict(TRIM, id=f"tr-{i:010d}-terse", request=f"cut the first {i} seconds") for i in range(n)
    ]


def _policy(tasks, good=True):
    by = {t["request"]: t for t in tasks}

    def pol(messages):
        t = by[json.loads(messages[1]["content"])["request"]]
        if good:
            return ReferenceTeacher(t)(messages)
        return json.dumps({"action": "unsupported", "reason": "no", "nearest_supported": None})

    return pol


def _run(tmp_path, corpus, monkeypatch, tasks, **kw):
    monkeypatch.setattr(run_mod, "corpus", lambda: corpus)
    guard = BudgetGuard(tmp_path / "ledger.jsonl", 4.0, 1.0, "t", dry_run=True)
    args = dict(workers=2, chunk=2, gate=0.82, gate_min_n=2, sleep=lambda s: None)
    return run_mod.bulk(tasks, tmp_path / "w", kw.pop("policy"), guard, **(args | kw))


def test_bulk_runs_chunks_to_completion(tmp_path, corpus, monkeypatch):
    tasks = _tasks(5)
    assert _run(tmp_path, corpus, monkeypatch, tasks, policy=_policy(tasks)) == "complete"
    rows = [json.loads(x) for x in (tmp_path / "w" / "chunks.jsonl").read_text().splitlines()]
    assert [r["attempted"] for r in rows] == [2, 2, 1, 0] and all(
        r["kept_rate"] == 1.0 for r in rows[:3]
    )


def test_bulk_stops_when_a_chunk_is_below_the_gate(tmp_path, corpus, monkeypatch):
    tasks = _tasks(6)
    assert _run(tmp_path, corpus, monkeypatch, tasks, policy=_policy(tasks, good=False)) == "gate"
    assert (
        len((tmp_path / "w" / "chunks.jsonl").read_text().splitlines()) == 1
    )  # stopped after the first chunk


def test_bulk_sleeps_through_a_peak_window_then_resumes(tmp_path, corpus, monkeypatch):
    tasks = _tasks(2)
    clock = [
        datetime(2026, 11, 20, 0, 59, tzinfo=UTC)
    ]  # 5-minute margin: a new episode may not start
    slept = []

    def sleep(s):
        slept.append(s)
        clock[0] += timedelta(seconds=s)

    why = _run(
        tmp_path,
        corpus,
        monkeypatch,
        tasks,
        policy=_policy(tasks),
        sleep=sleep,
        now=lambda: clock[0],
    )
    assert (
        why == "complete" and slept and slept[0] >= 3 * 3600 - 5 * 60
    )  # until 04:00 minus the margin
    assert clock[0].hour == 4 or clock[0].hour == 3
