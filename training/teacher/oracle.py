"""Programmatic "oracle" teacher: plays each TRAIN task's own gold spec and reference command (free, deterministic).

Not the plan's DeepSeek teacher and not a replacement for it: oracle trajectories are perfect but canonical (one solution
per content, lossless-first), so they carry no diversity of approach. Uses here: (1) end-to-end pipeline smoke tests
before any paid call, (2) a candidate extra/fallback SFT source the owner can approve (docs: D-032 proposal).
Never used on dev/test tasks (generate() refuses non-train splits).
"""

import json


class OraclePolicy:
    def __init__(self, tasks: list[dict]):
        self.by_request = {(t["request"], tuple(t["inputs"])): t for t in tasks}

    def _task(self, messages: list[dict]) -> dict:
        first = json.loads(messages[1]["content"])
        return self.by_request[(first["request"], tuple(i["id"] for i in first["inputs"]))]

    def __call__(self, messages: list[dict]) -> str:
        t = self._task(messages)
        turn = (len(messages) - 2) // 2
        if t["flags"]["ambiguous"]:
            return json.dumps(
                {
                    "action": "ask_user",
                    "question": "What exactly should be changed, and by how much?",
                }
            )
        if t["flags"]["unsupported"]:
            return json.dumps(
                {
                    "action": "unsupported",
                    "reason": "This needs editing the picture content, which FFmpeg operations cannot do.",
                    "nearest_supported": t.get("nearest_supported"),
                }
            )
        steps = [
            {"action": "spec", "spec": t["gold_spec"]},
            t["reference_runs"][0],
            {
                "action": "finish",
                "outputs": [o["id"] for o in t["gold_spec"]["outputs"]],
                "note": "Done: the output passed its check.",
            },
        ]
        return json.dumps(steps[min(turn, 2)])
