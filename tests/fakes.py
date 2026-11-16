"""Shared fakes for teacher/SFT tests: one train task and a policy that plays its own gold spec."""

import json

TRIM = {
    "id": "tr-aaaaaaaaaa-terse",
    "split": "train",
    "source": "taskgen-1.0",
    "request": "cut the first 2 seconds off this video",
    "inputs": ["h264_long"],
    "gold_spec": {
        "family": ["F1"],
        "outputs": [
            {
                "id": "out1",
                "kind": "video",
                "container": "mp4",
                "time": {"start_s": 2, "end_s": None, "tolerance_s": 0.15},
            }
        ],
    },
    "families": ["F1"],
    "difficulty": 1,
    "flags": {"ambiguous": False, "unsupported": False},
    "clarification": None,
    "reference_runs": [
        {
            "action": "run",
            "args": ["-ss", "2", "-i", "{in:h264_long}", "-c", "copy", "{out:out1}"],
            "inputs": ["h264_long"],
            "outputs": ["out1"],
        }
    ],
}


class ReferenceTeacher:
    """Plays the task's own gold spec and reference command (stands in for DeepSeek)."""

    def __init__(self, task):
        self.task = task

    def __call__(self, messages):
        turn = (len(messages) - 2) // 2
        t = self.task
        return json.dumps(
            [
                {"action": "spec", "spec": t["gold_spec"]},
                t["reference_runs"][0],
                {"action": "finish", "outputs": ["out1"], "note": "done"},
            ][min(turn, 2)]
        )
