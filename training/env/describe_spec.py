"""Plain-language description of a spec for user confirmation (D-008, plan T23).

The model proposes a spec, the person reads THIS text and confirms, and only then does the checker use that spec.
One line per field that is set; unconstrained (null) fields are not mentioned. The TypeScript UI (Phase 2) must
reproduce packages/protocol/conformance/describe-spec.jsonl line for line.
"""

_KIND = {
    "video": "a video",
    "audio": "an audio file",
    "image_sequence": "a set of images",
    "gif": "a GIF",
}
_ROT = {
    90: "turned 90 degrees to the right (clockwise)",
    180: "turned upside down (180 degrees)",
    270: "turned 90 degrees to the left (counterclockwise)",
    0: "not rotated",
}


_CODEC = {
    "h264": "H.264",
    "hevc": "HEVC (H.265)",
    "vp9": "VP9",
    "aac": "AAC",
    "mp3": "MP3",
    "opus": "Opus",
}


def _clock(s: float) -> str:
    total = int(round(s))
    return f"{total // 60}:{total % 60:02d}"


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def _size(n: int) -> str:
    return f"{n / 1_000_000:g} MB" if n >= 1_000_000 else f"{n / 1000:g} KB"


def describe_output(o: dict) -> list[str]:
    lines = [
        f"Result: {_KIND.get(o['kind'], o['kind'])}"
        + (f" ({o['container'].upper()})" if o.get("container") else "")
    ]
    v = {k: x for k, x in (o.get("video") or {}).items() if x is not None}
    if "width" in v and "height" in v:
        lines.append(f"Picture size: {v['width']} x {v['height']} pixels")
    elif "height" in v:
        lines.append(f"Picture height: {v['height']} pixels")
    elif "width" in v:
        lines.append(f"Picture width: {v['width']} pixels")
    if "rotation" in v:
        lines.append(f"Rotation: picture {_ROT[v['rotation']]}")
    if "fps" in v:
        lines.append(f"Frame rate: {_num(v['fps'])} frames per second")
    if "codec" in v:
        lines.append(f"Video codec: {_CODEC.get(v['codec'], v['codec'].upper())}")
    if "pix_fmt" in v:
        lines.append(f"Pixel format: {v['pix_fmt']}")
    a = {k: x for k, x in (o.get("audio") or {}).items() if x is not None}
    if a.get("present") is False:
        lines.append("Sound: removed")
    elif a.get("present") is True:
        lines.append("Sound: kept")
    if "codec" in a:
        lines.append(f"Audio codec: {_CODEC.get(a['codec'], a['codec'].upper())}")
    if "loudness_lufs" in a:
        lines.append(f"Loudness: about {_num(a['loudness_lufs'])} LUFS")
    if "offset_ms" in a:
        ms = a["offset_ms"]
        lines.append(
            "Sound and picture in sync"
            if ms == 0
            else f"Sound starts {_num(abs(ms))} ms {'later' if ms > 0 else 'earlier'} than the picture"
        )
    t = {k: x for k, x in (o.get("time") or {}).items() if x is not None and k != "tolerance_s"}
    if "start_s" in t and "end_s" in t:
        lines.append(f"Keep from {_clock(t['start_s'])} to {_clock(t['end_s'])}")
    elif "start_s" in t:
        lines.append(f"Start at {_clock(t['start_s'])} and keep the rest")
    elif "end_s" in t:
        lines.append(f"Length: about {_num(t['end_s'])} seconds")
    if o.get("size_max_bytes") is not None:
        lines.append(f"File size: at most {_size(o['size_max_bytes'])}")
    f = {k: x for k, x in (o.get("frames") or {}).items() if x is not None}
    if "interval_s" in f:
        count = f" ({f['expected_count']} images)" if "expected_count" in f else ""
        lines.append(f"One image every {_num(f['interval_s'])} seconds{count}")
    elif "expected_count" in f:
        lines.append(f"{f['expected_count']} image" + ("s" if f["expected_count"] != 1 else ""))
    if "format" in f:
        lines.append(f"Image format: {f['format'].upper()}")
    if o.get("lossless"):
        lines.append("No re-encoding: the picture quality is untouched")
    q = {k: x for k, x in (o.get("quality") or {}).items() if x is not None}
    if q:
        lines.append("Picture quality must stay close to the original")
    return lines


def describe_spec(spec: dict) -> list[str]:
    out = []
    for i, o in enumerate(spec["outputs"]):
        lines = describe_output(o)
        out += (
            lines if len(spec["outputs"]) == 1 else [f"Output {i + 1}:", *["  " + x for x in lines]]
        )
    return out
