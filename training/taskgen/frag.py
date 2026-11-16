"""A task draft as a small plan (trim, filters, output kind, gold-spec patch) from which BOTH the gold spec and the
executable reference command are built, so single-family and composed tasks share one code path.

Reference commands are what a careful human would write: stream copy whenever a lossless solution exists, else
libx264/aac. They are never shown to a model; they are executed by `verify_draft` against the checker, and they
define the "unnecessary re-encode" ground truth (EVALUATION §4.1).
"""

import copy
from dataclasses import dataclass, field

from training import config

# vf ordering: trim happens at input; then speed/fps, crop/scale, rotation.
ORDER = {"fps": 10, "speed": 15, "scale": 20, "rotate": 30}


@dataclass
class Draft:
    families: list[str]
    inputs: list[str]
    intents: list[str]
    kind: str = "video"  # video | audio | gif | image_sequence
    container: str | None = "mp4"
    trim: tuple[float | None, float | None] | None = None  # (start_s, end_s) in the input
    vf: list[tuple[str, str]] = field(default_factory=list)  # (stage, filter)
    af: list[str] = field(default_factory=list)
    drop_audio: bool = False
    copy_mode: str = "auto"  # auto | stream (lossless remux) | display_rotation
    rotation_cw: int | None = None  # lossless metadata rotation to write
    merge: bool = False
    offset_shift_ms: float | None = (
        None  # audio shifted by this much (itsoffset on the audio input)
    )
    bitrate_kbps: int | None = None
    gif_width: int | None = None
    frames_interval: float | None = None
    frames_fmt: str = "png"
    speed: float | None = None
    spec: dict = field(default_factory=dict)  # patch merged into the gold output spec
    slots: dict = field(default_factory=dict)  # values the phrasing templates fill
    difficulty: int = 1

    @property
    def output_id(self) -> str:
        return "out1"  # one id for every kind: the id must not reveal the output kind to the model


def deep_merge(a: dict, b: dict) -> dict | None:
    """Merge b into a copy of a; None on a conflicting leaf (two different values for one field)."""
    out = copy.deepcopy(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            merged = deep_merge(out[k], v)
            if merged is None:
                return None
            out[k] = merged
        elif k in out and out[k] is not None and v is not None and out[k] != v:
            return None
        else:
            out[k] = v if v is not None or k not in out else out[k]
    return out


def gold_spec(d: Draft) -> dict:
    out = {
        "id": d.output_id,
        "kind": d.kind,
        "container": d.container if d.kind != "image_sequence" else None,
    }
    merged = deep_merge(out, d.spec)
    assert merged is not None
    return {"family": list(d.families), "outputs": [merged]}


def _fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def _vf_chain(d: Draft) -> list[str]:
    return [f for _, f in sorted(d.vf, key=lambda sf: ORDER[sf[0]])]


def build_args(
    d: Draft, has_audio: dict[str, bool], rotate_spelling: str | None = None
) -> list[str]:
    """The reference command (arguments without `ffmpeg`)."""
    rotate_spelling = rotate_spelling or config.LOSSLESS_ROTATE_SPELLING
    out = [f"{{out:{d.output_id}}}"]
    ins = [f"{{in:{c}}}" for c in d.inputs]
    ss = []
    if d.trim and not d.merge:
        s, e = d.trim
        ss += ["-ss", _fmt(s or 0)]
    tl = []
    if d.trim and not d.merge and d.trim[1] is not None:
        tl += ["-t", _fmt(d.trim[1] - (d.trim[0] or 0))]
    if (
        d.speed and tl
    ):  # with a speed change -t must limit what is READ (input side), not the sped-up output
        ss, tl = [*ss, *tl], []
    audio = has_audio[d.inputs[0]] and not d.drop_audio

    if (
        d.offset_shift_ms is not None
    ):  # audio input shifted by itsoffset, video from the unshifted one
        sec = _fmt(d.offset_shift_ms / 1000)
        return [
            "-i",
            ins[0],
            "-itsoffset",
            sec,
            "-i",
            ins[0],
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c",
            "copy",
            *out,
        ]

    if d.kind == "image_sequence":
        return [*ss, "-i", ins[0], *tl, "-vf", f"fps=1/{_fmt(d.frames_interval)}", *out] if d.frames_interval else [
            *ss, "-i", ins[0], "-frames:v", "1", *out]  # fmt: skip
    if d.kind == "gif":
        w = d.gif_width or 320
        fc = f"fps=10,scale={w}:-1,split[x][y];[x]palettegen[p];[y][p]paletteuse"
        return [*ss, "-i", ins[0], *tl, "-filter_complex", fc, *out]
    if d.kind == "audio":
        af = ["-af", ",".join(d.af)] if d.af else []
        return [*ss, "-i", ins[0], *tl, "-vn", *af, "-c:a", "libmp3lame", "-b:a", "192k", *out]

    if d.merge:
        n = len(ins)
        a = all(has_audio[c] for c in d.inputs) and not d.drop_audio
        legs = "".join(f"[{i}:v]" + (f"[{i}:a]" if a else "") for i in range(n))
        fc = f"{legs}concat=n={n}:v=1:a={1 if a else 0}[v]" + ("[a]" if a else "")
        vf = _vf_chain(d)
        maps = ["-map", "[v]"]
        if vf:
            fc += f";[v]{','.join(vf)}[vo]"
            maps = ["-map", "[vo]"]
        if a:
            if d.af:
                fc += f";[a]{','.join(d.af)}[ao]"
            maps += ["-map", "[ao]" if d.af else "[a]"]
        return [
            *[x for i in ins for x in ("-i", i)],
            "-filter_complex",
            fc,
            *maps,
            *_codec(d, True, a),
            *out,
        ]

    vf, af = _vf_chain(d), list(d.af)
    lossless_copy = (
        d.copy_mode in ("stream", "display_rotation")
        and not vf
        and not af
        and d.bitrate_kbps is None
    )
    if lossless_copy:
        pre = []
        if d.copy_mode == "display_rotation" and d.rotation_cw is not None:
            ccw = (-d.rotation_cw) % 360  # FFmpeg's matrix angle is counterclockwise
            ccw = ccw - 360 if ccw > 180 else ccw
            if rotate_spelling == "display_rotation":
                pre = ["-display_rotation", str(ccw)]
        mid = ["-metadata:s:v:0", f"rotate={(-d.rotation_cw) % 360}"] if (
            d.copy_mode == "display_rotation" and rotate_spelling == "metadata_rotate") else []  # fmt: skip
        drop = ["-an"] if d.drop_audio else []
        return [*pre, *ss, "-i", ins[0], *tl, *drop, "-c", "copy", *mid, *out]
    vfa = ["-vf", ",".join(vf)] if vf else []
    afa = ["-af", ",".join(af)] if (af and audio) else []
    return [*ss, "-i", ins[0], *tl, *vfa, *afa, *_codec(d, False, audio), *out]


def _codec(d: Draft, merged: bool, audio: bool) -> list[str]:
    v = ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    if d.bitrate_kbps:
        v += [
            "-b:v",
            f"{d.bitrate_kbps}k",
            "-maxrate",
            f"{d.bitrate_kbps}k",
            "-bufsize",
            f"{2 * d.bitrate_kbps}k",
        ]
    else:
        v += ["-crf", "23"]
    a = (
        ["-c:a", "aac"] + (["-b:a", "64k"] if d.bitrate_kbps else [])
        if audio
        else (["-an"] if d.drop_audio and not merged else [])
    )
    return v + a
