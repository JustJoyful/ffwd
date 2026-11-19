import json

from fakes import TRIM

from training.env.loop import run_episode, score
from training.taskgen.verify import content_key
from training.teacher.generate import generate
from training.teacher.oracle import OraclePolicy

AMB = dict(
    TRIM,
    id="tr-amb0000000-terse",
    request="make it shorter",
    flags={"ambiguous": True, "unsupported": False},
    gold_spec=None,
    reference_runs=None,
    clarification="keep 5 s",
)
UNS = dict(
    TRIM,
    id="tr-uns0000000-terse",
    request="remove the person",
    flags={"ambiguous": False, "unsupported": True},
    gold_spec=None,
    reference_runs=None,
    families=[],
    nearest_supported=None,
    # the label check recovers the intent from the content key, so a synthetic task needs a real one
    content_key=content_key([], TRIM["inputs"], {"unsup": "unsup.subtitles"}),
)


def test_oracle_solves_graded_ambiguous_and_unsupported_tasks(corpus, tmp_path):
    tasks = [TRIM, AMB, UNS]
    summary = generate(
        tasks, tmp_path / "o", OraclePolicy(tasks), None, corpus, allow_draft_prompt=True
    )
    assert (summary.attempted, summary.kept) == (3, 3)
    kept = {
        json.loads(x)["task_id"]: json.loads(x)
        for x in (tmp_path / "o" / "kept.jsonl").read_text().splitlines()
    }
    assert kept[TRIM["id"]]["end_reason"] == "finish" and kept[AMB["id"]]["end_reason"] == "asked"
    assert kept[UNS["id"]]["end_reason"] == "unsupported" and kept[TRIM["id"]]["runs"] == 1


def test_oracle_runs_through_the_phase1_loop_options(corpus, tmp_path):
    ep = run_episode(
        TRIM,
        OraclePolicy([TRIM]),
        corpus=corpus,
        job_dir=tmp_path,
        require_spec=True,
        stop_after_ask=True,
    )
    assert score(TRIM, ep) and ep.emitted_spec == TRIM["gold_spec"] and ep.invalid_turns == 0


def test_select_oracle_tops_up_unsupported_categories_within_the_share_cap():
    import json as _json
    from collections import Counter

    from training import config
    from training.taskgen.special import unsupported_intent
    from training.teacher.oracle import select_oracle

    tasks = [
        _json.loads(x)
        for x in (config.DATA_DIR / "tasks" / "train" / "v1.jsonl").read_text().splitlines()
    ]
    plain = [t for t in tasks if not t["flags"]["unsupported"]][:1000]
    kept = [
        {"task_id": t["id"]} for t in plain
    ]  # a teacher that solved 1000 supported tasks and no unsupported ones
    picked = select_oracle(tasks, kept, min_per_category=20)
    assert len(picked) == int(0.29 * 1000 / 0.71) and len({t["id"] for t in picked}) == len(picked)
    per = Counter(unsupported_intent(t) for t in picked if t["flags"]["unsupported"])
    assert len(per) == 9 and all(v >= 20 for v in per.values())
    assert len(picked) / (len(picked) + len(kept)) <= 0.30
    assert [t["id"] for t in picked] == [
        t["id"] for t in select_oracle(tasks, kept, min_per_category=20)
    ]
