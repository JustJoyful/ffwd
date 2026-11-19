"""Ambiguous tasks (expect `ask_user`) and unsupported tasks (expect `unsupported`) (D-009).

Ambiguous: gold_spec null; `clarification` is what the simulated user answers when asked. The episode scores as a
pass only if the model asked before running (loop.score). Unsupported: no family, gold_spec null; `nearest_supported`
is the closest family the agent may name (or null).
"""

import random

from training.taskgen.clips import ClipIndex
from training.taskgen.verify import content_key

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

# Labels a teacher may give as `nearest_supported` (D-009; teacher pilot 19 Nov 2026). Strict by default: only the
# canonical value above. "upscale ... to 4K" really is the F4 resize (scale) with the AI part refused, while "make this
# blurry footage sharp" has no supported neighbour (no sharpen/denoise filter in the allowlist), so that one intent
# accepts both. "Give me a transcript" also accepts F9: extracting the audio is the supported step toward it (the bulk
# teacher answered F9 on 3/3). The pilot's "blur everyone's face" -> F4 stays a mismatch: cropping does not blur; so do
# colour grade -> F3 and background -> F3/F4 (the bulk teacher's other habits): nothing supported is close there.
NEAREST_ACCEPTED: dict[str, frozenset[str | None]] = {
    intent: frozenset({near}) for intent, near in UNSUPPORTED.items()
} | {"unsup.upscale": frozenset({"F4", None}), "unsup.transcribe": frozenset({"F9", None})}


def unsupported_intent(task: dict) -> str | None:
    """The intent behind a stored unsupported task. The task files keep neither the intent nor `nearest_supported`, but
    the content key is sha256(families, inputs, {"unsup": intent}), so the intent is recovered exactly (no rebuild).
    """
    return next(
        (
            i
            for i in UNSUPPORTED
            if content_key([], task["inputs"], {"unsup": i}) == task["content_key"]
        ),
        None,
    )


def nearest_ok(task: dict, given: str | None) -> bool:
    """Is the teacher's `nearest_supported` acceptable for this unsupported task? Unknown intent -> not ok."""
    intent = unsupported_intent(task)
    return intent is not None and given in NEAREST_ACCEPTED[intent]


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
