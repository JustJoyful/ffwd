import json
import random

import pytest
from fakes import TRIM, ReferenceTeacher

from training.sft.rejection import rejection_sample


def easy(task_id, request, difficulty=1):
    return dict(TRIM, id=task_id, request=request, difficulty=difficulty)


class Flaky:
    """Passes about half the time (a wrong trim otherwise)."""

    def __init__(self, task, rng):
        self.task, self.rng, self.good = task, rng, None
        self.teacher = ReferenceTeacher(task)

    def __call__(self, messages):
        turn = (len(messages) - 2) // 2
        if self.good is None:
            self.good = self.rng.random() < 0.5
        if not self.good and turn == 1:
            bad = dict(
                self.task["reference_runs"][0],
                args=["-ss", "9", "-i", "{in:h264_long}", "-c", "copy", "{out:out1}"],
            )
            return json.dumps(bad)
        return self.teacher(messages)


def test_only_passing_and_distinct_runs_are_kept_and_hard_tasks_skipped(corpus, tmp_path):
    t1, hard = easy("tr-1111111111-terse", "cut two seconds"), easy(
        "tr-2222222222-terse", "cut some more", difficulty=3
    )
    rng = random.Random(0)
    stats = rejection_sample(
        [t1, hard], lambda: Flaky(t1, rng), corpus, tmp_path / "rej", n=6, allow_draft_prompt=True
    )
    assert stats["attempted"] == 6  # the difficulty-3 task was never sampled
    kept = [json.loads(x) for x in (tmp_path / "rej" / "kept.jsonl").read_text().splitlines()]
    assert 0 < len(kept) <= 6 and all(r["passed"] for r in kept)
    assert stats["distinct"] == len(kept) == 1  # identical passing transcripts collapse to one


def test_non_train_tasks_are_refused(corpus, tmp_path):
    with pytest.raises(PermissionError):
        rejection_sample(
            [dict(TRIM, split="dev")],
            lambda: ReferenceTeacher(TRIM),
            corpus,
            tmp_path,
            allow_draft_prompt=True,
        )
