"""Compositions of 2-4 chore families (PRD multi-step; EVALUATION: test-compositional).

Two drafts merge into one when their plans and gold specs do not conflict; the merged draft gets ONE reference
command (filters chained) that is verified like any other. `COMPOSABLE` keeps the combinations realistic:
nobody asks for "extract frames AND compress to 2 MB". Unlisted pairs are never generated.
"""

import itertools
import random
from collections.abc import Callable

from training.env.checker import expected_frame_range
from training.taskgen.clips import ClipIndex
from training.taskgen.families import SAMPLERS
from training.taskgen.frag import Draft, deep_merge

COMPOSABLE: dict[str, set[str]] = {
    "F1": {"F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F12"},
    "F2": {"F3", "F4", "F9"},
    "F3": {"F1", "F2", "F4", "F9", "F12"},
    "F4": {"F1", "F2", "F3", "F5", "F6", "F9", "F10", "F12"},
    "F5": {"F1", "F4", "F9", "F12"},
    "F6": {"F1", "F4", "F9"},
    "F7": {"F1"},
    "F8": {"F1"},
    "F9": {"F1", "F2", "F3", "F4", "F5", "F6", "F10", "F12"},
    "F10": {"F1", "F4", "F9"},
    "F11": set(),
    "F12": {"F1", "F3", "F4", "F5", "F9"},
}


def valid_combo(fams: tuple[str, ...]) -> bool:
    return all(b in COMPOSABLE[a] for a, b in itertools.combinations(fams, 2))


def valid_combos(k: int) -> list[tuple[str, ...]]:
    return [
        c
        for c in itertools.combinations(sorted(COMPOSABLE, key=lambda f: int(f[1:])), k)
        if valid_combo(c)
    ]


def _window(d: Draft, ci: ClipIndex) -> float:
    c = ci[d.inputs[0]]
    s, e = d.trim if d.trim else (0, None)
    return (e if e is not None else c.duration_s) - (s or 0)


def compose(drafts: list[Draft], ci: ClipIndex) -> Draft | None:
    first = drafts[0]
    out = Draft(families=[], inputs=list(first.inputs), intents=[])
    out.merge = any(d.merge for d in drafts)
    kinds = {d.kind for d in drafts} - {"video"}
    if len(kinds) > 1:
        return None
    out.kind = kinds.pop() if kinds else "video"
    out.container = next(
        (d.container for d in drafts if d.kind == out.kind and out.kind != "video"), "mp4"
    )
    out.copy_mode = "auto"
    spec: dict = {}
    stages: dict[str, str] = {}
    for d in drafts:
        out.families += d.families
        out.intents += d.intents
        if d.merge and d is not first and d.inputs != out.inputs:
            return None
        if d.trim:
            if out.trim:
                return None  # two trims would be ambiguous
            out.trim = d.trim
        for stage, f in d.vf:
            if stages.get(stage, f) != f:
                return None
            stages[stage] = f
        out.af += d.af
        out.drop_audio |= d.drop_audio
        if d.copy_mode == "display_rotation":
            out.copy_mode, out.rotation_cw = "display_rotation", d.rotation_cw
        for k, v in d.slots.items():
            if out.slots.get(k, v) != v:
                return None
            out.slots[k] = v
        for k in ("speed", "gif_width", "frames_interval", "bitrate_kbps"):
            if getattr(d, k) is not None:
                setattr(out, k, getattr(d, k))
        out.frames_fmt = d.frames_fmt if d.kind == "image_sequence" else out.frames_fmt
        dspec = {k: v for k, v in d.spec.items() if k != "time"}
        merged = deep_merge(spec, dspec)
        if merged is None:
            return None
        spec = merged
    out.vf = list(stages.items())
    aud = spec.get("audio") or {}
    if out.drop_audio and any(
        aud.get(k) is not None for k in ("loudness_lufs", "offset_ms", "codec")
    ):
        return None  # "remove the sound" and "set its loudness" contradict each other
    if out.kind == "audio" and ({"video", "lossless", "size_max_bytes"} & set(spec)):
        return None  # an audio file has no picture to resize/rotate/compress
    if out.copy_mode == "display_rotation" and (out.vf or out.af or out.speed or out.bitrate_kbps):
        return None  # a lossless metadata rotation cannot coexist with re-encoding operations
    if out.kind in ("audio", "image_sequence", "gif") and out.vf and out.kind != "gif":
        return None  # video filters make no sense for audio output; frames are sampled directly
    if out.kind == "gif" and out.vf:
        return None
    # time: trim positions, a speed change, or both (then the spec states the new length, per prompt v1)
    trim_len = _window(out, ci) if out.trim else None
    if out.speed:
        base = trim_len if trim_len is not None else ci[out.inputs[0]].duration_s
        spec["time"] = {"start_s": None, "end_s": round(base / out.speed, 3), "tolerance_s": 0.2}
    elif out.trim:
        s, e = out.trim
        spec["time"] = {
            "start_s": s,
            "end_s": e,
            "tolerance_s": 0.15 if out.kind == "video" else 0.2,
        }
    if out.merge and out.trim:
        return None
    if out.kind == "image_sequence" and out.frames_interval:
        lo, hi = expected_frame_range(
            trim_len or ci[out.inputs[0]].duration_s, out.frames_interval, ci[out.inputs[0]].fps
        )
        if lo != hi or hi < 2:
            return None
        spec["frames"] = {
            "interval_s": out.frames_interval,
            "expected_count": hi,
            "format": out.frames_fmt,
        }
        spec.pop("time", None)  # frames are checked by count, not duration
    if out.bitrate_kbps and out.trim:
        c = ci[first.inputs[0]]
        target = spec["size_max_bytes"]
        out.bitrate_kbps = int((target * 8 * 0.85) / trim_len / 1000) - 64
        if out.bitrate_kbps < 150 or target > 0.5 * c.size_bytes * trim_len / c.duration_s:
            return None
    if out.copy_mode == "auto" and set(out.families) <= {"F1", "F9"} and not out.af and not out.vf:
        out.copy_mode = "stream"
    out.spec, out.difficulty = spec, len(out.families)
    return out


def sample_composition(
    rng: random.Random,
    ci: ClipIndex,
    n_families: int,
    tries: int = 40,
    combo_weight: Callable[[tuple[str, ...]], float] | None = None,
) -> Draft | None:
    """2-4 families on one input; None if no valid, verifiable-looking composition was found.
    `combo_weight` (hard-variant pool only) biases which valid combination is drawn; the default path is unchanged.
    """
    combos = valid_combos(n_families)
    if not combos:
        return None
    for _ in range(tries):
        combo = list(
            rng.choice(combos)
            if combo_weight is None
            else rng.choices(combos, weights=[combo_weight(c) for c in combos])[0]
        )
        rng.shuffle(combo)  # which family anchors the clip choice varies
        base = SAMPLERS[combo[0]](rng, ci)
        if base is None:
            continue
        drafts = [base]
        for f in combo[1:]:
            d = SAMPLERS[f](rng, ci, clip=None if base.merge else base.inputs[0])
            if d is None:
                break
            drafts.append(d)
        else:
            merged = compose(drafts, ci)
            if merged is not None:
                return merged
    return None
