"""Deterministic checker v0 (RULES §4.3: code, not a model; ARCH §3.4).

Checks only spec fields that are set (null = unconstrained). Never raises on bad media: a probe
failure or empty output becomes passed=False with `error` set.
Covers video/audio/time/size/frames/re-encode plus loudness (EBU R128), A/V offset (first-packet
timestamps: verifies the requested shift was applied, not perceived sync), net rotation measured from
content, and IMPLICIT invariants (v1.2): unless the spec changes them, output duration and audio
presence equal the input's (so a 0.1 s clip can never satisfy "make it play on PowerPoint").
Quality floor is still to come. Tolerances and their evidence live in training/config.py.
"""

import math
import re
import subprocess
from pathlib import Path

from training import config
from training.env.ffmpeg_pin import ffmpeg_bin
from training.env.orientation import net_rotation_cw
from training.env.probe import display_size, first_packet_pts, probe
from training.env.quality import measure_quality
from training.env.validator import uses_stream_copy_only

# shortcut: container is a substring match on ffprobe's format_name, which cannot tell mp4 from
# mov ("mov,mp4,m4a,..."); compare major_brand in checker v1 if that distinction matters.
_CONTAINER_ALIASES = {"mkv": "matroska", "m4a": "mp4"}


def _result(checks: list[dict], measurements: dict, error: str | None = None) -> dict:
    passed = error is None and all(c["ok"] for c in checks)
    return {"passed": passed, "checks": checks, "measurements": measurements, "error": error}


def _add(checks: list[dict], field: str, expected, actual, ok: bool) -> None:
    checks.append({"field": field, "expected": expected, "actual": actual, "ok": bool(ok)})


def expected_frame_range(
    duration_s: float, interval_s: float, fps: float | None
) -> tuple[int, int]:
    """(min, max) accepted frame count for "one frame every interval_s" over duration_s (counting rule in
    training/config.py): samples at t = k * interval, kept while t < duration - 0.5 frame. The max is the
    strict count; the min is one lower when the last sample is within half an interval of the end.
    """
    last = duration_s - config.FRAME_SAMPLE_EPS_FRAMES / (fps or 30.0)
    strict = max(1, math.ceil(last / interval_s - 1e-9))
    boundary = last - (strict - 1) * interval_s < interval_s / 2
    return (max(1, strict - 1) if boundary else strict), strict


def _check_frames(spec: dict, out_dir: Path, input_probe: dict, measurements: dict) -> dict:
    frames = spec.get("frames") or {}
    fmt = frames.get("format")
    files = sorted(f for f in out_dir.iterdir() if f.is_file()) if out_dir.is_dir() else []
    measurements["frame_count"] = len(files)
    if not files:
        return _result([], measurements, "no frames written")
    checks: list[dict] = []
    expected = frames.get("expected_count")
    if expected is not None:
        ok = abs(len(files) - expected) <= config.FRAME_COUNT_TOLERANCE
        _add(checks, "frames.expected_count", expected, len(files), ok)
    elif frames.get("interval_s") and input_probe.get("duration_s"):
        vid = next((s for s in input_probe["streams"] if s["type"] == "video"), {})
        lo, hi = expected_frame_range(
            input_probe["duration_s"], frames["interval_s"], vid.get("fps")
        )
        _add(checks, "frames.count_for_interval", f"{lo}..{hi}", len(files), lo <= len(files) <= hi)
    if fmt:
        exts = sorted({f.suffix.lstrip(".") for f in files})
        _add(checks, "frames.format", fmt, exts, exts == [fmt])
    return _result(checks, measurements)


_LUFS = re.compile(r"^\s+I:\s+(-?[\d.]+|-inf) LUFS", re.MULTILINE)


def _integrated_loudness(path: Path) -> float | None:
    argv = [
        ffmpeg_bin(),
        "-hide_banner",
        "-nostdin",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-af",
        "ebur128=framelog=-8",  # numeric AV_LOG_QUIET: the name `quiet` does not exist in FFmpeg 5.1 (D-024)
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
    if (
        proc.returncode != 0
    ):  # a failed filter graph still prints a zero summary: never read it as a measurement
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


def _input_offset_ms(input_paths: list[Path] | None) -> float:
    """|audio start - video start| of the first input in ms (0 when unmeasurable)."""
    if not input_paths:
        return 0.0
    v0, a0 = first_packet_pts(input_paths[0], "video"), first_packet_pts(input_paths[0], "audio")
    return abs((a0 - v0) * 1000) if v0 is not None and a0 is not None else 0.0


def _implicit_checks(
    out_spec: dict,
    p: dict,
    vids: list,
    auds: list,
    input_probes: list[dict],
    checks: list[dict],
    input_paths: list[Path] | None = None,
) -> None:
    """Invariants every output must keep unless the spec says otherwise (v1.2)."""
    kind = out_spec["kind"]
    if kind == "video":
        _add(checks, "implicit.video_stream", True, bool(vids), bool(vids))
    if kind == "audio":
        _add(checks, "implicit.audio_stream", True, bool(auds), bool(auds))
    audio = out_spec.get("audio") or {}
    if kind == "video" and audio.get("present") is None:
        expected = any(s["type"] == "audio" for ip in input_probes for s in ip["streams"])
        _add(checks, "implicit.audio_present", expected, bool(auds), bool(auds) == expected)
    t = out_spec.get("time") or {}
    if kind != "image_sequence" and t.get("start_s") is None and t.get("end_s") is None:
        durations = [ip.get("duration_s") for ip in input_probes]
        if durations and all(d is not None for d in durations):
            expected = sum(durations)  # one output from several inputs = their concatenation
            tol = t.get("tolerance_s")
            tol = config.IMPLICIT_DURATION_TOLERANCE_S if tol is None else tol
            if audio.get("offset_ms") is not None:
                # Shifting audio stretches/shrinks the container by the shift: allow the target offset plus the
                # input's own offset (an "audio is 0.5 s late, fix it" task targets 0 but removes 0.5 s).
                tol += (abs(audio["offset_ms"]) + _input_offset_ms(input_paths)) / 1000
            ok = abs(p["duration_s"] - expected) <= tol
            _add(checks, "implicit.duration_s", expected, p["duration_s"], ok)


def _quality_applies(out_spec: dict, input_probe: dict) -> bool:
    """Default floor: a size-target video that keeps the input's timeline and framing (so frames are
    comparable). Trimmed or reframed outputs are exempt unless the spec states a quality explicitly.
    """
    t, video = out_spec.get("time") or {}, out_spec.get("video") or {}
    inp = next((s for s in input_probe["streams"] if s["type"] == "video"), None)
    if out_spec.get("size_max_bytes") is None or out_spec["kind"] != "video" or inp is None:
        return False
    if t.get("start_s") is not None or t.get("end_s") is not None:
        return False
    w, h = display_size(inp)
    return all(video.get(k) in (None, v) for k, v in (("width", w), ("height", h)))


def _quality_checks(out_spec, output, input_probe, input_paths, checks, measurements, vids) -> None:
    explicit = {k: v for k, v in (out_spec.get("quality") or {}).items() if v is not None}
    floors = dict(explicit)
    if not floors and _quality_applies(out_spec, input_probe):
        floors = {
            "min_ssim": config.SSIM_FLOOR_DEFAULT,
            "min_psnr_db": config.PSNR_FLOOR_DB_DEFAULT,
        }
    if not floors:
        return
    inp = next((s for s in input_probe["streams"] if s["type"] == "video"), None)
    q = None
    if vids and inp and input_paths:
        w, h = display_size(inp)
        q = measure_quality(input_paths[0], output, w, h)
    measurements["quality"] = q
    for key, field in (("min_ssim", "ssim"), ("min_psnr_db", "psnr_db")):
        if key in floors:
            actual = q[field] if q else None
            _add(
                checks,
                f"quality.{key}",
                floors[key],
                actual,
                actual is not None and actual >= floors[key],
            )


def check(
    out_spec: dict,
    output: Path,
    *,
    input_probe: dict,
    run_args: list[str],
    input_probes: list[dict] | None = None,
    input_paths: list[Path] | None = None,
) -> dict:
    """input_probes/input_paths: every input in task order (default: just `input_probe`). input_paths is
    needed for `video.rotation`, which is measured against the input's picture."""
    input_probes = input_probes or [input_probe]
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
            ):
                if key in video:
                    _add(checks, f"video.{key}", video[key], actual, actual == video[key])
            if "rotation" in video:
                net = net_rotation_cw(input_paths[0], output) if input_paths else None
                measurements["net_rotation_cw"] = net
                _add(checks, "video.rotation", video["rotation"], net, net == video["rotation"])
            if "fps" in video:
                fps = v["fps"]
                ok = (
                    fps is not None
                    and abs(fps - video["fps"]) <= config.FPS_REL_TOLERANCE * video["fps"]
                )
                _add(checks, "video.fps", video["fps"], fps, ok)

    _implicit_checks(out_spec, p, vids, auds, input_probes, checks, input_paths)

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
        if vids and auds:
            # First-packet timestamps, not stream start_time: see first_packet_pts (edit-list clamping
            # made a correct audio advance read as 0.0, a false negative found in Phase 0).
            v0, a0 = first_packet_pts(output, "video"), first_packet_pts(output, "audio")
            if v0 is not None and a0 is not None:
                offset = round((a0 - v0) * 1000, 1)
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

    _quality_checks(out_spec, output, input_probe, input_paths, checks, measurements, vids)

    if out_spec.get("lossless"):
        _add(
            checks, "lossless", True, not measurements["re_encoded"], not measurements["re_encoded"]
        )

    return _result(checks, measurements)
