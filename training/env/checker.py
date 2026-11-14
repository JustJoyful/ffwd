"""Deterministic checker v0 (RULES §4.3: code, not a model; ARCH §3.4).

Checks only spec fields that are set (null = unconstrained). Never raises on bad media: a probe
failure or empty output becomes passed=False with `error` set.
v0 covers video/audio/time/size/frames/re-encode plus loudness (EBU R128) and A/V offset
(stream start times: verifies the requested shift was applied, not perceived sync). Quality floor is v1.
"""

import math
import re
import subprocess
from pathlib import Path

from training import config
from training.env.probe import display_size, probe
from training.env.validator import uses_stream_copy_only

# shortcut: container is a substring match on ffprobe's format_name, which cannot tell mp4 from
# mov ("mov,mp4,m4a,..."); compare major_brand in checker v1 if that distinction matters.
_CONTAINER_ALIASES = {"mkv": "matroska", "m4a": "mp4"}


def _result(checks: list[dict], measurements: dict, error: str | None = None) -> dict:
    passed = error is None and all(c["ok"] for c in checks)
    return {"passed": passed, "checks": checks, "measurements": measurements, "error": error}


def _add(checks: list[dict], field: str, expected, actual, ok: bool) -> None:
    checks.append({"field": field, "expected": expected, "actual": actual, "ok": bool(ok)})


def _check_frames(spec: dict, out_dir: Path, input_probe: dict, measurements: dict) -> dict:
    frames = spec.get("frames") or {}
    fmt = frames.get("format")
    files = sorted(f for f in out_dir.iterdir() if f.is_file()) if out_dir.is_dir() else []
    measurements["frame_count"] = len(files)
    if not files:
        return _result([], measurements, "no frames written")
    checks: list[dict] = []
    expected = frames.get("expected_count")
    if expected is None and frames.get("interval_s") and input_probe.get("duration_s"):
        expected = math.floor(input_probe["duration_s"] / frames["interval_s"])
    if expected is not None:
        ok = abs(len(files) - expected) <= config.FRAME_COUNT_TOLERANCE
        _add(checks, "frames.expected_count", expected, len(files), ok)
    if fmt:
        exts = sorted({f.suffix.lstrip(".") for f in files})
        _add(checks, "frames.format", fmt, exts, exts == [fmt])
    return _result(checks, measurements)


_LUFS = re.compile(r"^\s+I:\s+(-?[\d.]+|-inf) LUFS", re.MULTILINE)


def _integrated_loudness(path: Path) -> float | None:
    argv = [
        config.FFMPEG_BIN,
        "-hide_banner",
        "-nostdin",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-af",
        "ebur128=framelog=quiet",
        "-f",
        "null",
        "-",
    ]
    try:
        proc = subprocess.run(argv, shell=False, capture_output=True, timeout=config.RUN_TIMEOUT_S)
    except (
        subprocess.SubprocessError,
        OSError,
    ):  # unmeasurable loudness fails the field, never raises
        return None
    found = _LUFS.findall(proc.stderr.decode(errors="replace"))
    return float(found[-1]) if found and found[-1] != "-inf" else None


def _expected_duration(t: dict, input_probe: dict) -> float | None:
    start, end = t.get("start_s"), t.get("end_s")
    if start is not None and end is not None:
        return end - start
    if start is not None and input_probe.get("duration_s") is not None:
        return input_probe["duration_s"] - start
    return end


def check(out_spec: dict, output: Path, *, input_probe: dict, run_args: list[str]) -> dict:
    measurements: dict = {"re_encoded": not uses_stream_copy_only(run_args)}
    if out_spec["kind"] == "image_sequence":
        return _check_frames(out_spec, output, input_probe, measurements)
    try:
        if not output.is_file() or output.stat().st_size == 0:
            return _result([], measurements, "output missing or empty")
        p = probe(output)
    except Exception as e:  # corrupt media must fail the check, not crash the episode
        return _result([], measurements, f"probe failed: {type(e).__name__}")
    measurements["duration_s"] = p["duration_s"]
    if not p["duration_s"] or not p["streams"]:
        return _result([], measurements, "output has no media")

    checks: list[dict] = []
    vids = [s for s in p["streams"] if s["type"] == "video"]
    auds = [s for s in p["streams"] if s["type"] == "audio"]

    if container := out_spec.get("container"):
        name = _CONTAINER_ALIASES.get(container, container)
        _add(checks, "container", container, p["container"], name in p["container"].split(","))

    video = {k: v for k, v in (out_spec.get("video") or {}).items() if v is not None}
    if video:
        if not vids:
            _add(checks, "video", "present", None, False)
        else:
            v = vids[0]
            w, h = display_size(v)
            for key, actual in (
                ("codec", v["codec"]),
                ("pix_fmt", v["pix_fmt"]),
                ("width", w),
                ("height", h),
                ("rotation", v["rotation"]),
            ):
                if key in video:
                    _add(checks, f"video.{key}", video[key], actual, actual == video[key])
            if "fps" in video:
                fps = v["fps"]
                ok = (
                    fps is not None
                    and abs(fps - video["fps"]) <= config.FPS_REL_TOLERANCE * video["fps"]
                )
                _add(checks, "video.fps", video["fps"], fps, ok)

    audio = {k: v for k, v in (out_spec.get("audio") or {}).items() if v is not None}
    if "present" in audio:
        _add(checks, "audio.present", audio["present"], bool(auds), bool(auds) == audio["present"])
    if "codec" in audio:
        actual = auds[0]["codec"] if auds else None
        _add(checks, "audio.codec", audio["codec"], actual, actual == audio["codec"])

    if "loudness_lufs" in audio:
        lufs = _integrated_loudness(output) if auds else None
        measurements["loudness_lufs"] = lufs
        ok = lufs is not None and abs(lufs - audio["loudness_lufs"]) <= config.LOUDNESS_TOLERANCE_LU
        _add(checks, "audio.loudness_lufs", audio["loudness_lufs"], lufs, ok)
    if "offset_ms" in audio:
        offset = None
        if vids and auds and None not in (vids[0]["start_time_s"], auds[0]["start_time_s"]):
            offset = round((auds[0]["start_time_s"] - vids[0]["start_time_s"]) * 1000, 1)
        measurements["offset_ms"] = offset
        ok = offset is not None and abs(offset - audio["offset_ms"]) <= config.OFFSET_TOLERANCE_MS
        _add(checks, "audio.offset_ms", audio["offset_ms"], offset, ok)

    t = out_spec.get("time") or {}
    expected = _expected_duration(t, input_probe)
    if expected is not None:
        tol = (
            t.get("tolerance_s")
            if t.get("tolerance_s") is not None
            else config.DEFAULT_TIME_TOLERANCE_S
        )
        _add(
            checks,
            "time.duration_s",
            expected,
            p["duration_s"],
            abs(p["duration_s"] - expected) <= tol,
        )

    if (cap := out_spec.get("size_max_bytes")) is not None:
        _add(checks, "size_max_bytes", cap, p["size_bytes"], p["size_bytes"] <= cap)

    if out_spec.get("lossless"):
        _add(
            checks, "lossless", True, not measurements["re_encoded"], not measurements["re_encoded"]
        )

    return _result(checks, measurements)
