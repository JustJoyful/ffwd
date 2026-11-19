import dataclasses
import json
from datetime import UTC, datetime, timedelta

import pytest
from fakes import TRIM, ReferenceTeacher  # noqa: E402

from training import config
from training.env.loop import run_episode
from training.taskgen.special import (
    NEAREST_ACCEPTED,
    UNSUPPORTED,
    nearest_ok,
    unsupported_intent,
)
from training.taskgen.verify import content_key
from training.teacher.budget import BudgetExceeded
from training.teacher.datacard import build_card
from training.teacher.generate import OffPeakRequired, PromptNotFrozen, generate, is_offpeak


class Switch:
    """One policy object across tasks: looks the task up by the request text in the first user message."""

    def __init__(self, tasks, bad=()):
        self.by_request = {t["request"]: t for t in tasks}
        self.bad = set(bad)

    def __call__(self, messages):
        req = json.loads(messages[1]["content"])["request"]
        if req in self.bad:
            return json.dumps({"action": "unsupported", "reason": "no", "nearest_supported": None})
        return ReferenceTeacher(self.by_request[req])(messages)


def _gen(tmp_path, corpus, tasks, policy, **kw):
    return generate(tasks, tmp_path / "out", policy, None, corpus, allow_draft_prompt=True, **kw)


def test_teacher_never_sees_gold_spec_or_reference(corpus, tmp_path):
    seen = []
    teacher = ReferenceTeacher(TRIM)

    def spy(messages):
        seen.append(json.dumps(messages[:2]))
        return teacher(messages)

    _gen(tmp_path, corpus, [TRIM], spy)
    blob = seen[0]
    assert (
        json.dumps(TRIM["gold_spec"]) not in blob
        and json.dumps(TRIM["gold_spec"]).replace('"', '\\"') not in blob
    )
    ref_args = json.dumps(TRIM["reference_runs"][0]["args"])
    assert ref_args not in blob and ref_args.replace('"', '\\"') not in blob
    assert "cut the first 2 seconds" in blob and "duration_s" in blob


def test_only_passing_trajectories_are_kept(corpus, tmp_path):
    bad = dict(TRIM, id="tr-bbbbbbbbbb-terse", request="remove the first 2 seconds please")
    s = _gen(tmp_path, corpus, [TRIM, bad], Switch([TRIM, bad], bad={bad["request"]}))
    assert (s.attempted, s.kept) == (2, 1)
    kept = [json.loads(x) for x in (tmp_path / "out" / "kept.jsonl").read_text().splitlines()]
    allr = [
        json.loads(x) for x in (tmp_path / "out" / "trajectories.jsonl").read_text().splitlines()
    ]
    assert [r["task_id"] for r in kept] == [TRIM["id"]] and len(allr) == 2 and not allr[1]["passed"]


def test_resume_skips_finished_tasks(corpus, tmp_path):
    _gen(tmp_path, corpus, [TRIM], ReferenceTeacher(TRIM))
    s = _gen(tmp_path, corpus, [TRIM], ReferenceTeacher(TRIM))
    assert s.attempted == 0 and s.skipped_done == 1
    assert len((tmp_path / "out" / "trajectories.jsonl").read_text().splitlines()) == 1


def test_draft_or_edited_prompt_and_non_train_splits_are_refused(corpus, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SYSTEM_PROMPT_V1_SHA256", None)  # a draft prompt
    with pytest.raises(PromptNotFrozen):
        generate([TRIM], tmp_path / "o", ReferenceTeacher(TRIM), None, corpus)
    monkeypatch.setattr(
        config, "SYSTEM_PROMPT_V1_SHA256", "0" * 64
    )  # the file no longer matches its pinned hash
    with pytest.raises(PromptNotFrozen, match="no longer matches"):
        generate([TRIM], tmp_path / "o", ReferenceTeacher(TRIM), None, corpus)
    monkeypatch.undo()
    with pytest.raises(PermissionError):
        _gen(tmp_path, corpus, [dict(TRIM, split="dev")], ReferenceTeacher(TRIM))


def test_offpeak_gate_with_a_fake_clock(corpus, tmp_path):
    at = lambda h, m=0: datetime(2026, 11, 16, h, m, tzinfo=UTC)  # noqa: E731
    assert not is_offpeak(at(1)) and not is_offpeak(at(3, 59)) and is_offpeak(at(4))
    assert is_offpeak(at(5, 59)) and not is_offpeak(at(6)) and not is_offpeak(at(9, 59))
    assert is_offpeak(at(10)) and is_offpeak(at(23)) and is_offpeak(at(0))
    with pytest.raises(OffPeakRequired):
        _gen(tmp_path, corpus, [TRIM], ReferenceTeacher(TRIM), offpeak_only=True, now=lambda: at(2))
    s = _gen(
        tmp_path, corpus, [TRIM], ReferenceTeacher(TRIM), offpeak_only=True, now=lambda: at(23)
    )
    assert s.kept == 1


def test_budget_exceeded_stops_cleanly_keeping_earlier_results(corpus, tmp_path):
    second = dict(TRIM, id="tr-cccccccccc-terse", request="drop the first 2 seconds")
    teacher = Switch([TRIM, second])
    calls = {"n": 0}

    def flaky(messages):
        calls["n"] += 1
        if json.loads(messages[1]["content"])["request"] == second["request"]:
            raise BudgetExceeded("cap")
        return teacher(messages)

    s = _gen(tmp_path, corpus, [TRIM, second], flaky)
    assert s.kept == 1 and s.stopped.startswith("budget")


def test_datacard_flags_missing_terms(corpus, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TEACHER_TERMS_URL", None)
    monkeypatch.setattr(config, "TEACHER_TERMS_SNAPSHOT_SHA256", None)
    s = _gen(tmp_path, corpus, [TRIM], ReferenceTeacher(TRIM))
    card = json.loads(build_card(tmp_path / "out", dataclasses.asdict(s)).read_text())
    assert card["status"].startswith("INCOMPLETE") and card["kept_trajectories"] == 1
    assert card["teacher_model"] == config.DEEPSEEK_MODEL_ID


def test_datacard_quotes_section_4_2_from_the_saved_snapshot_and_detects_tampering(
    corpus, tmp_path, monkeypatch
):
    s = _gen(tmp_path, corpus, [TRIM], ReferenceTeacher(TRIM))
    card = json.loads(build_card(tmp_path / "out", dataclasses.asdict(s)).read_text())
    ev = card["terms_evidence"]
    assert card["status"] == "complete"
    assert (
        ev["open_platform_tos_release_date"] == "April 22, 2026"
        and ev["open_platform_tos_effective_date"] == "April 29, 2026"
    )
    assert "(2) We assign any rights, title, and interests" in ev["open_platform_tos_section_4_2"]
    assert (
        "training other models (such as model distillation)" in ev["open_platform_tos_section_4_2"]
    )
    assert ev["owner_confirmation"].startswith("Read §4.2 myself on 2026-11-19")
    monkeypatch.setattr(config, "TEACHER_TERMS_SNAPSHOT_SHA256", "0" * 64)
    assert (
        build_card(tmp_path / "out", dataclasses.asdict(s)).read_text().count("no longer match")
        == 1
    )


def test_loop_options_used_by_generate_are_the_phase1_ones(corpus, tmp_path):
    ep = run_episode(
        TRIM,
        ReferenceTeacher(TRIM),
        corpus=corpus,
        job_dir=tmp_path,
        require_spec=True,
        stop_after_ask=True,
    )
    assert ep.end_reason == "finish" and ep.emitted_spec == TRIM["gold_spec"]


# --- bulk-run additions: nearest_supported filter, workers, clean stop at peak ------------------------------------


def _unsup(intent: str, tid: str) -> dict:
    return dict(
        TRIM, id=tid, request=f"do {intent}", flags={"ambiguous": False, "unsupported": True}, gold_spec=None,
        reference_runs=None, families=[], content_key=content_key([], TRIM["inputs"], {"unsup": intent}),
    )  # fmt: skip


def _says(near):
    return lambda messages: json.dumps(
        {"action": "unsupported", "reason": "no", "nearest_supported": near}
    )


def test_unsupported_label_is_filtered_not_edited(corpus, tmp_path):
    blur = _unsup(
        "unsup.blur_faces", "tr-blur000000-terse"
    )  # gold null, the pilot's wrong answer was F4
    s = _gen(tmp_path, corpus, [blur], _says("F4"))
    assert (s.attempted, s.passed, s.kept, s.label_rejected) == (1, 1, 0, 1)
    rec = json.loads((tmp_path / "out" / "trajectories.jsonl").read_text())
    assert (
        rec["passed"] and not rec["label_ok"]
    )  # the raw record keeps the teacher's answer verbatim
    assert "F4" in rec["messages"][2]["content"] and not (tmp_path / "out" / "kept.jsonl").exists()
    ok = _gen(tmp_path / "b", corpus, [blur], _says(None))
    assert (ok.passed, ok.kept, ok.label_rejected) == (1, 1, 0)


def test_upscale_accepts_f4_or_null_everything_else_is_strict():
    assert NEAREST_ACCEPTED["unsup.upscale"] == {"F4", None}
    assert all(NEAREST_ACCEPTED[i] == {UNSUPPORTED[i]} for i in UNSUPPORTED if i != "unsup.upscale")


def test_every_unsupported_train_task_resolves_to_an_intent():
    rows = [
        json.loads(x)
        for x in (config.DATA_DIR / "tasks" / "train" / "v1.jsonl").read_text().splitlines()
    ]
    uns = [t for t in rows if t["flags"]["unsupported"]]
    assert uns and all(unsupported_intent(t) in UNSUPPORTED for t in uns)
    assert not nearest_ok(uns[0], "F9")


def test_parallel_workers_match_sequential_and_cost_is_per_episode(corpus, tmp_path):
    tasks = [
        dict(TRIM, id=f"tr-{i:010d}-terse", request=f"cut the first {i} seconds")
        for i in range(1, 5)
    ]
    a = generate(
        tasks, tmp_path / "a", Switch(tasks), None, corpus, allow_draft_prompt=True, workers=1
    )
    b = generate(
        tasks, tmp_path / "b", Switch(tasks), None, corpus, allow_draft_prompt=True, workers=3
    )
    assert (a.attempted, a.kept) == (b.attempted, b.kept) == (4, 4)

    def ids(d):
        return [
            json.loads(x)["task_id"]
            for x in (tmp_path / d / "trajectories.jsonl").read_text().splitlines()
        ]

    assert ids("a") == ids("b")


def test_stop_on_peak_is_clean_and_resumable(corpus, tmp_path):
    peak = datetime(
        2026, 11, 20, 0, 58, tzinfo=UTC
    )  # inside the 5-minute margin before the 01:00 window
    s = _gen(
        tmp_path,
        corpus,
        [TRIM],
        ReferenceTeacher(TRIM),
        offpeak_only=True,
        now=lambda: peak,
        stop_on_peak=True,
    )
    assert s.stopped == "peak window" and s.attempted == 0
    with pytest.raises(OffPeakRequired):
        _gen(tmp_path, corpus, [TRIM], ReferenceTeacher(TRIM), offpeak_only=True, now=lambda: peak)
    later = peak - timedelta(minutes=30)
    assert (
        _gen(
            tmp_path, corpus, [TRIM], ReferenceTeacher(TRIM), offpeak_only=True, now=lambda: later
        ).kept
        == 1
    )
