"""HELD-OUT phrasing styles for test-phrasing (D-027). Imported only by taskgen.build (via phrasing.render).
Do NOT read this file when writing baselines (B0) or training data: its wording is the generalisation test.

context_first (owner-approved replacement for the earlier `technical` style): a situation first, then the
problem statement, never an explicit command ("for my viva tomorrow, ppt won't play this").
indirect: a goal first, then the explicit request.
"""

import random

HELDOUT_STYLES = ("context_first", "indirect")

_SITUATIONS = [
    "for my viva tomorrow, ",
    "the college portal keeps rejecting my upload and ",
    "my cousin's old TV just shows a black screen, ",
    "the group chat won't let me send this, ",
    "I'm sitting in the library with bad wifi and ",
]
_GOALS = [
    "I'm posting this online later, so ",
    "before I send this to a friend, ",
    "for my presentation tomorrow, ",
    "my phone is almost out of space, so ",
]


def render(intents: list[str], slots: dict, style: str, rng: random.Random) -> str:
    from training.taskgen.phrasing import BANK  # noqa: PLC0415

    if style == "context_first":
        first = rng.choice(BANK[intents[0]]["symptom"]).format(**slots)
        rest = [rng.choice(BANK[i]["cont"]).format(**slots) for i in intents[1:]]
        first = first[0].lower() + first[1:] if first[:2] not in ("I ", "I'") else first
        return rng.choice(_SITUATIONS) + first + "".join(f", and {r}" for r in rest)
    if style == "indirect":
        cores = [BANK[it]["core"][0].format(**slots) for it in intents]
        return rng.choice(_GOALS) + " and ".join(cores)
    raise ValueError(f"unknown style {style!r}")
