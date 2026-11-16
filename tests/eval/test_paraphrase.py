import json

from eval.paraphrase import clean, numbers, paraphrase_tasks
from training import config

TASKS = [
    json.loads(x) for x in (config.DATA_DIR / "tasks/dev/spike-v0.jsonl").read_text().splitlines()
][:3]


def test_numbers_compare_as_multiset():
    assert numbers("keep 0:12 to 0:18") == numbers("from 0:18 to 0:12 only")
    assert numbers("2 MB") != numbers("3 MB")


def test_clean_strips_quotes_and_extra_lines():
    assert clean('"Trim 3 seconds."\nextra') == "Trim 3 seconds."


def test_keeps_only_matching_and_judged_paraphrases():
    by_req = {
        TASKS[0]["request"]: "chop the first 3 seconds from this clip",  # ok
        TASKS[1]["request"]: "keep 0:12 to 0:20",  # digits differ
        TASKS[2]["request"]: TASKS[2]["request"],  # unchanged
    }
    kept, log = paraphrase_tasks(TASKS, lambda r: by_req[r], lambda p: "YES")
    assert [t["id"] for t in kept] == [TASKS[0]["id"]]
    assert kept[0]["original_request"] == TASKS[0]["request"] and kept[0]["gold_spec"]
    assert [r["dropped"] for r in log] == [None, "digits differ", "empty or unchanged"]


def test_judge_no_drops():
    kept, log = paraphrase_tasks(
        TASKS[:1], lambda r: "chop 3 seconds off the start", lambda p: "NO"
    )
    assert not kept and log[0]["dropped"].startswith("judge")
