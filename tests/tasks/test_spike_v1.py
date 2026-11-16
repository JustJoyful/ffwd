"""spike-v1: derived from spike-v0 (frozen) + the owner's new tasks (ids n01.., source spike-v1-new)."""

import hashlib
import json

import pytest

from eval.verify_tasks import verify_task
from training import config
from training.protocol import validate

DEV = config.DATA_DIR / "tasks" / "dev"
V0_SHA256 = (
    "25e9d18e2ddf486aa44f261c62fc168322c77c0808333838fa85943d516c0489"  # eval/PREREGISTRATION.md
)
TASKS = [json.loads(x) for x in (DEV / "spike-v1.jsonl").read_text().splitlines()]
ORIGINAL = [t for t in TASKS if t["source"] == "spike-v0"]
NEW = [t for t in TASKS if t["source"] == "spike-v1-new"]
BY_ID = {t["id"]: t for t in TASKS}


def test_v0_file_is_untouched():
    assert hashlib.sha256((DEV / "spike-v0.jsonl").read_bytes()).hexdigest() == V0_SHA256


def test_originals_are_v0_minus_m05():
    v0 = [json.loads(x)["id"] for x in (DEV / "spike-v0.jsonl").read_text().splitlines()]
    assert [t["id"] for t in ORIGINAL] == [i for i in v0 if i != "m05-merge-mute"]
    assert len({t["id"] for t in TASKS}) == len(TASKS) and {t["source"] for t in TASKS} <= {
        "spike-v0",
        "spike-v1-new",
    }
    assert all(t["id"].startswith("n") for t in NEW)


def test_unsupported_tasks_belong_to_no_family():
    unsupported = [t for t in TASKS if t["flags"]["unsupported"]]
    assert len(unsupported) >= 3
    assert all(t["families"] == [] and t["nearest_supported"] is None for t in unsupported)
    assert all(t["families"] for t in TASKS if not t["flags"]["unsupported"])


def test_interval_tasks_pin_interval_and_count():
    for tid, (interval, count) in {
        "s19-frame-every-2s": (2, 5),
        "s20-every-second-jpg": (1, 10),
        "m03-frames-2-to-7": (1, 5),
    }.items():
        frames = BY_ID[tid]["gold_spec"]["outputs"][0]["frames"]
        assert (frames["interval_s"], frames["expected_count"]) == (interval, count), tid


def test_rotation_golds_use_the_clockwise_convention():
    rot = lambda tid: BY_ID[tid]["gold_spec"]["outputs"][0]["video"]["rotation"]  # noqa: E731
    assert (rot("s13-rotate-cw-lossless"), rot("s14-upside-down"), rot("s15-turn-left")) == (
        90,
        180,
        270,
    )
    assert rot("m09-rotate-cw-30fps") == 90


@pytest.mark.parametrize("task", TASKS, ids=[t["id"] for t in TASKS])
def test_schema_valid(task):
    assert validate("task", task) == []
    flagged = task["flags"]["ambiguous"] or task["flags"]["unsupported"]
    assert (task["gold_spec"] is None) == flagged and (task["reference_runs"] is None) == flagged


GRADED = [t for t in TASKS if t["gold_spec"]]


@pytest.mark.parametrize("task", GRADED, ids=[t["id"] for t in GRADED])
def test_reference_solution_passes_its_gold_spec(task, corpus, tmp_path):
    row = verify_task(task, corpus, tmp_path)
    assert row["passed"], row["failed"]
