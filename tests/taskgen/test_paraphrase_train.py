import json

from fakes import TRIM, ReferenceTeacher

from training.taskgen.paraphrase import paraphrase_train, rounds, with_request
from training.teacher.budget import BudgetExceeded
from training.teacher.generate import generate


def _kept(corpus, tmp_path, tasks):
    pol = {t["request"]: t for t in tasks}
    generate(
        tasks, tmp_path / "o",
        lambda m: ReferenceTeacher(pol[json.loads(m[1]["content"])["request"]])(m),
        None, corpus, allow_draft_prompt=True,
    )  # fmt: skip
    return [json.loads(x) for x in (tmp_path / "o" / "kept.jsonl").read_text().splitlines()]


def _tasks(n):
    return [
        dict(
            TRIM,
            id=f"tr-aaaaaaaaaa-w{i}",
            request="cut the first 2 seconds " + "abcdefgh"[i],
            content_key="k" * 64,
        )
        for i in range(n)
    ]


def test_paraphrase_is_a_copy_with_only_the_request_changed(corpus, tmp_path):
    tasks = _tasks(1)
    rec = _kept(corpus, tmp_path, tasks)[0]
    before = json.dumps(rec)
    new = with_request(rec, "trim off the first 2 seconds", 1)
    assert json.dumps(rec) == before  # the original record is not touched
    assert new["task_id"] == f"{rec['task_id']}+p1" and new["messages"][2:] == rec["messages"][2:]
    a, b = json.loads(rec["messages"][1]["content"]), json.loads(new["messages"][1]["content"])
    assert b["request"] == "trim off the first 2 seconds" and {**b, "request": 0} == {
        **a,
        "request": 0,
    }
    assert new["original_request"] == a["request"] and new["source"] == "teacher-paraphrase"


def test_rounds_take_one_wording_per_content_per_round(corpus, tmp_path):
    tasks = _tasks(3)  # same content_key (TRIM's), three wordings
    kept = _kept(corpus, tmp_path, tasks)
    by_id = {t["id"]: t for t in tasks}
    assert [len(r) for r in rounds(kept, by_id, 2)] == [1, 1]


def test_digit_rule_judge_and_budget_stop_apply(corpus, tmp_path):
    tasks = _tasks(3)
    kept, by_id = _kept(corpus, tmp_path, tasks), {t["id"]: t for t in tasks}
    ok = paraphrase_train(
        kept, by_id, lambda r: "take away the first 2 seconds", lambda p: "YES", per_content=2
    )
    assert len(ok[0]) == 2 and ok[2] is None
    bad_digits = paraphrase_train(
        kept, by_id, lambda r: "take away the first 3 seconds", lambda p: "YES"
    )
    assert bad_digits[0] == [] and bad_digits[1][0]["dropped"] == "digits differ"
    no_judge = paraphrase_train(
        kept, by_id, lambda r: "take away the first 2 seconds", lambda p: "NO"
    )
    assert no_judge[0] == []

    def broke(r):
        raise BudgetExceeded("cap")

    out, _, why = paraphrase_train(kept, by_id, broke, lambda p: "YES")
    assert out == [] and why.startswith("budget")
    _, _, why = paraphrase_train(
        kept, by_id, lambda r: "x", lambda p: "YES", may_start=lambda: False
    )
    assert why == "peak window"
