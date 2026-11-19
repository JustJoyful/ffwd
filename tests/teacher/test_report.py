import json

from training import config
from training.taskgen.special import unsupported_intent
from training.teacher.report import analyse


def _row(task, near, passed=True):
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "{}"}]
    msgs += [
        {"role": "assistant", "content": json.dumps({"action": "unsupported", "reason": "r", "nearest_supported": near})},
        {"role": "user", "content": json.dumps({"ended": "unsupported"})},
    ]  # fmt: skip
    return {"task_id": task["id"], "passed": passed, "invalid_turns": 0, "messages": msgs}


def test_analyse_counts_unsupported_labels_after_filtering():
    tasks = [
        json.loads(x)
        for x in (config.DATA_DIR / "tasks" / "train" / "v1.jsonl").read_text().splitlines()
    ]
    blur = next(
        t
        for t in tasks
        if t["flags"]["unsupported"] and unsupported_intent(t) == "unsup.blur_faces"
    )
    up = next(
        t for t in tasks if t["flags"]["unsupported"] and unsupported_intent(t) == "unsup.upscale"
    )
    a = analyse([_row(blur, "F4"), _row(up, "F4"), _row(up, None), _row(up, "F9")], tasks)
    assert (
        a["total"]["passed"] == 4 and a["total"]["kept"] == 2
    )  # blur->F4 and upscale->F9 are filtered
    assert (
        a["unsupported"][("unsup.upscale", "kept")] == 2
        and a["unsupported"][("unsup.blur_faces", "kept")] == 0
    )
    assert a["labels"][("unsup.blur_faces", "F4", False)] == 1
