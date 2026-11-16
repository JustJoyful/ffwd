"""HELD-OUT phrasing styles for test-phrasing (D-027). Imported only by taskgen.build (via phrasing.render).
Do NOT read this file when writing baselines (B0) or training data: its wording is the generalisation test.

technical: FFmpeg-flavoured wording. indirect: the goal/context first, the request second.
"""

import random

HELDOUT_STYLES = ("technical", "indirect")

TECH = {
    "f1": ["re-mux with a start offset and duration set so the output keeps the requested span"],
    "f2": ["concatenate the inputs in order into one stream"],
    "f3": ["transcode to H.264 yuv420p with AAC audio in an MP4 container"],
    "f4": ["re-scale the video stream to the target frame size"],
    "f5": ["apply the display rotation so the picture is rotated"],
    "f6": ["re-encode to a bitrate that keeps the output under the size cap"],
    "f7": ["decode to a still-image sequence at the given interval"],
    "f8": ["encode a palette-based GIF at the given width"],
    "f9": ["demux the audio stream"],
    "f10": ["apply a gain / EBU R128 loudness filter to the audio stream"],
    "f11": ["shift the audio stream timestamps relative to the video"],
    "f12": ["change the presentation timestamps or the output frame rate"],
}
_GOALS = [
    "I'm posting this online later, so ",
    "before I send this to a friend, ",
    "for my presentation tomorrow, ",
    "my phone is almost out of space, so ",
]


def render(intents: list[str], slots: dict, style: str, rng: random.Random) -> str:
    from training.taskgen.phrasing import BANK  # noqa: PLC0415

    if style == "technical":
        pieces = []
        for it in intents:
            fam = it.split(".")[0]
            base = BANK[it]["core"][0].format(**slots)
            pieces.append(f"{rng.choice(TECH[fam])}: {base}")
        return "; ".join(pieces)
    if style == "indirect":
        cores = [BANK[it]["core"][0].format(**slots) for it in intents]
        return rng.choice(_GOALS) + " and ".join(cores)
    raise ValueError(f"unknown style {style!r}")
