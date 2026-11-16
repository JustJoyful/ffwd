"""Ambiguous tasks (expect `ask_user`) and unsupported tasks (expect `unsupported`) (D-009).

Ambiguous: gold_spec null; `clarification` is what the simulated user answers when asked. The episode scores as a
pass only if the model asked before running (loop.score). Unsupported: no family, gold_spec null; `nearest_supported`
is the closest family the agent may name (or null).
"""

import random

from training.taskgen.clips import ClipIndex

# intent -> (nominal family for bookkeeping, simulated user's answer)
AMBIGUOUS = {
    "amb.shorter": ("F1", "keep the first 10 seconds"),
    "amb.smaller": ("F6", "under 5 MB"),
    "amb.fix": ("F3", "it won't play on my TV, I need a normal MP4"),
    "amb.trim": ("F1", "cut the first 2 seconds"),
    "amb.convert": ("F3", "to an MP4 that plays everywhere"),
    "amb.audio": ("F10", "it is too quiet, normalize it to -16 LUFS"),
}
UNSUPPORTED: dict[str, str | None] = {
    "unsup.remove_object": None,
    "unsup.subtitles": None,
    "unsup.colour_grade": None,
    "unsup.upscale": "F4",
    "unsup.background": None,
    "unsup.voice": None,
    "unsup.transcribe": None,
    "unsup.stabilize": None,
    "unsup.blur_faces": None,
}


def sample_ambiguous(rng: random.Random, ci: ClipIndex) -> dict:
    intent = rng.choice(sorted(AMBIGUOUS))
    fam, answer = AMBIGUOUS[intent]
    c = rng.choice(
        ci.pool(audio=True, vcodec="h264", min_s=4, exclude_tags=("vfr", "rotation", "av_offset"))
    )
    return {
        "intent": intent,
        "inputs": [c.id],
        "families": [fam],
        "clarification": answer,
        "ambiguous": True,
        "unsupported": False,
    }


def sample_unsupported(rng: random.Random, ci: ClipIndex) -> dict:
    intent = rng.choice(sorted(UNSUPPORTED))
    c = rng.choice(
        ci.pool(audio=True, vcodec="h264", min_s=4, exclude_tags=("vfr", "rotation", "av_offset"))
    )
    return {
        "intent": intent,
        "inputs": [c.id],
        "families": [],
        "nearest_supported": UNSUPPORTED[intent],
        "clarification": None,
        "ambiguous": False,
        "unsupported": True,
    }
