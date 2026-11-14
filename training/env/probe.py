"""ffprobe → normalised probe result (ARCH §3.3, probe.schema.json)."""

import json
import subprocess
from fractions import Fraction
from pathlib import Path

from training import config

_STREAM_TYPES = {"video", "audio", "subtitle", "data", "attachment"}


def _num(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _int(v: object) -> int | None:
    f = _num(v)
    return None if f is None else int(f)


def _fps(rate: str | None) -> float | None:
    if not rate or rate.startswith("0/") or rate.endswith("/0"):
        return None
    return float(Fraction(rate))


def _rotation(stream: dict) -> int:
    # ffprobe's displaymatrix rotation is counterclockwise degrees, possibly negative (-90 on
    # iPhone portrait clips). Normalise onto {0, 90, 180, 270}.
    for sd in stream.get("side_data_list", []):
        if "rotation" in sd:
            return round(float(sd["rotation"]) / 90) * 90 % 360
    return 0


def _stream(s: dict) -> dict:
    kind = s.get("codec_type") if s.get("codec_type") in _STREAM_TYPES else "unknown"
    out = {"index": s["index"], "type": kind, "codec": s.get("codec_name")}
    if kind == "video":
        out |= {
            "width": s.get("width"),
            "height": s.get("height"),
            "fps": _fps(s.get("avg_frame_rate")),
            "pix_fmt": s.get("pix_fmt"),
            "rotation": _rotation(s),
        }
    elif kind == "audio":
        out |= {"sample_rate": _int(s.get("sample_rate")), "channels": s.get("channels")}
    out |= {"start_time_s": _num(s.get("start_time")), "duration_s": _num(s.get("duration"))}
    return out


def probe(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    argv = [
        config.FFPROBE_BIN,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    raw = json.loads(subprocess.run(argv, shell=False, check=True, capture_output=True).stdout)
    fmt = raw.get("format", {})
    return {
        "container": fmt.get("format_name", ""),
        "duration_s": _num(fmt.get("duration")),
        "size_bytes": int(fmt.get("size", path.stat().st_size)),
        "bit_rate": _int(fmt.get("bit_rate")),
        "streams": [_stream(s) for s in raw.get("streams", [])],
    }


def display_size(stream: dict) -> tuple[int, int]:
    """Width/height as the viewer sees them (rotation 90/270 swaps the coded dimensions)."""
    w, h = stream["width"], stream["height"]
    return (h, w) if stream.get("rotation") in (90, 270) else (w, h)
