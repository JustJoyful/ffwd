"""Programmatic "oracle" teacher: plays each TRAIN task's own gold spec and reference command (free, deterministic).

Not the plan's DeepSeek teacher and not a replacement for it: oracle trajectories are perfect but canonical (one solution
per content, lossless-first), so they carry no diversity of approach. Uses here: (1) end-to-end pipeline smoke tests
before any paid call, (2) a candidate extra/fallback SFT source the owner can approve (docs: D-032 proposal).
Never used on dev/test tasks (generate() refuses non-train splits).
"""

import json
import random
from collections import Counter

from training.taskgen.special import UNSUPPORTED, unsupported_intent

# Why each unsupported intent cannot be done (shown as `reason`): one accurate line per intent, not a generic one.
UNSUPPORTED_REASON = {
    "unsup.remove_object": "Removing or erasing something in the picture needs content-aware editing, which FFmpeg operations cannot do.",
    "unsup.subtitles": "Subtitles need speech recognition and text rendering, which the supported FFmpeg operations do not include.",
    "unsup.colour_grade": "A creative colour grade is not among the supported operations.",
    "unsup.upscale": "AI upscaling or sharpening cannot be done with FFmpeg operations; plain resizing (F4) is supported but adds no detail.",
    "unsup.background": "Removing or replacing the background needs person segmentation, which FFmpeg operations cannot do.",
    "unsup.voice": "Changing or translating a voice needs speech models, which FFmpeg operations cannot do.",
    "unsup.transcribe": "Transcribing or summarizing speech needs a speech model, which FFmpeg operations cannot do.",
    "unsup.stabilize": "Stabilizing shaky footage needs motion analysis, which the supported FFmpeg operations do not include.",
    "unsup.blur_faces": "Blurring faces or plates needs object detection, which FFmpeg operations cannot do.",
}


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
            intent = unsupported_intent(
                t
            )  # the task files keep neither the intent nor the label; recovered exactly
            return json.dumps(
                {
                    "action": "unsupported",
                    "reason": UNSUPPORTED_REASON.get(
                        intent, "This is not among the supported FFmpeg operations."
                    ),
                    "nearest_supported": (
                        t["nearest_supported"]
                        if "nearest_supported" in t
                        else UNSUPPORTED.get(intent)
                    ),
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


def select_oracle(
    tasks: list[dict], kept: list[dict], *, min_per_category: int = 20, max_share: float = 0.29, seed: int = 20261115
) -> list[dict]:  # fmt: skip
    """Which TRAIN tasks to play through the oracle: at most `max_share` of the final mix (kept + oracle examples).
    1) top up every unsupported category with fewer than `min_per_category` kept trajectories (any unsupported task not
    already kept), 2) fill the rest with tasks whose CONTENT the teacher did not cover, shuffled and balanced across
    families round-robin. Deterministic. `kept`: the final kept records (paraphrase ids `<id>+pK` count as their source).
    """
    by_id = {t["id"]: t for t in tasks}
    kept_ids = {r["task_id"].split("+")[0] for r in kept}
    covered = {by_id[i]["content_key"] for i in kept_ids}
    have = Counter(
        unsupported_intent(by_id[i]) for i in kept_ids if by_id[i]["flags"]["unsupported"]
    )
    rng = random.Random(seed)
    pool = sorted(tasks, key=lambda t: t["id"])
    rng.shuffle(pool)
    budget = int(max_share * len(kept) / (1 - max_share))
    picked: list[dict] = []
    for intent in sorted(UNSUPPORTED):
        need = max(0, min_per_category - have[intent])
        picked += [
            t
            for t in pool
            if t["flags"]["unsupported"]
            and t["id"] not in kept_ids
            and unsupported_intent(t) == intent
        ][:need]
    picked = picked[:budget]
    taken = {t["id"] for t in picked}
    queues: dict[str, list[dict]] = {}
    for t in pool:
        if t["content_key"] not in covered and t["id"] not in taken:
            queues.setdefault("+".join(t["families"]) or "unsupported", []).append(t)
    ordered = [queues[k] for k in sorted(queues)]
    while len(picked) < budget and any(ordered):
        for q in ordered:
            if q and len(picked) < budget:
                picked.append(q.pop())
    return picked
