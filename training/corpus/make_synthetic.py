"""Deterministic synthetic mini corpus (PHASES Phase 0; ARCH §7.1).

Usage: uv run python -m training.corpus.make_synthetic data/corpus
Writes clips plus manifest.json (id, file, sha256, licence, source, probe).
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

from training import config
from training.env.probe import probe

LICENCE = "CC0-1.0 (synthetic, generated)"
# Same bytes on the same FFmpeg build: no encoder tags, no source metadata.
_STABLE = ["-fflags", "+bitexact", "-map_metadata", "-1", "-flags:v", "+bitexact"]
_X265_QUIET = ["-x265-params", "log-level=error"]


class ClipRecord(TypedDict):
    id: str
    file: str
    sha256: str
    licence: str
    source: str
    probe: dict
    tags: list[str]
    known_offset_ms: (
        float | None
    )  # nominal audio-minus-video start offset baked into the clip, else None


def _video(size: str, rate: int, seconds: float) -> list[str]:
    return ["-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration={seconds}"]


def _audio(seconds: float, volume_db: float = 0.0) -> list[str]:
    return [
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:sample_rate=48000:duration={seconds}," f"volume={volume_db}dB",
    ]


_H264 = ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
_AAC = ["-c:a", "aac", "-b:a", "96k"]

# id -> (filename, ffmpeg args after the binary, before the output path)
RECIPES: dict[str, tuple[str, list[str]]] = {
    "h264_aac_1080p": ("h264_aac_1080p.mp4", _video("1920x1080", 30, 4) + _audio(4) + _H264 + _AAC),
    "h264_vertical": ("h264_vertical.mp4", _video("1080x1920", 30, 4) + _audio(4) + _H264 + _AAC),
    "hevc_iphone": (
        "hevc_iphone.mov",
        _video("1920x1080", 30, 4)
        + _audio(4)
        + ["-c:v", "libx265", "-preset", "ultrafast", "-tag:v", "hvc1", *_X265_QUIET]
        + _AAC,
    ),
    "h264_noaudio": ("h264_noaudio.mp4", _video("1280x720", 30, 4) + _H264),
    "h264_quiet": ("h264_quiet.mp4", _video("1280x720", 30, 4) + _audio(4, -40) + _H264 + _AAC),
    "h264_25fps_720p": (
        "h264_25fps_720p.mp4",
        _video("1280x720", 25, 10) + _audio(10) + _H264 + _AAC,
    ),
    "vp9_opus_webm": (
        "vp9_opus_webm.webm",
        _video("640x360", 30, 4)
        + _audio(4)
        + ["-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8", "-c:a", "libopus"],
    ),
    "mpeg4_avi": (
        "mpeg4_avi.avi",
        _video("640x480", 25, 4) + _audio(4) + ["-c:v", "mpeg4", "-c:a", "libmp3lame"],
    ),
    "h264_long": ("h264_long.mp4", _video("1280x720", 30, 20) + _audio(20) + _H264 + _AAC),
    "clip_a": ("clip_a.mp4", _video("1280x720", 30, 3) + _audio(3) + _H264 + _AAC),
    "clip_b": ("clip_b.mp4", _video("1280x720", 30, 3) + _audio(3) + _H264 + _AAC),
}
# --- Corpus v1 additions (ARCH §7.1 coverage): VFR, 4:3, ProRes-lite, MKV, mono/44.1 kHz, noisy and offset audio.
# Existing recipes above are untouched, so their bytes and hashes do not change.
_VFR = [
    "-vf",
    "select='lt(mod(n,7),3)'",
    "-fps_mode",
    "vfr",
]  # keeps 3 of every 7 frames: irregular timestamps
RECIPES |= {
    "h264_vfr": ("h264_vfr.mp4", _video("1280x720", 30, 6) + _audio(6) + _VFR + _H264 + _AAC),
    "h264_4x3": ("h264_4x3.mp4", _video("640x480", 30, 5) + _audio(5) + _H264 + _AAC),
    "prores_lite": (
        "prores_lite.mov",
        _video("1280x720", 30, 3)
        + _audio(3)
        + ["-c:v", "prores_ks", "-profile:v", "0", "-pix_fmt", "yuv422p10le", "-c:a", "pcm_s16le"],
    ),
    "h264_mkv": ("h264_mkv.mkv", _video("1280x720", 30, 4) + _audio(4) + _H264 + _AAC),
    "h264_mono_44k": (
        "h264_mono_44k.mp4",
        _video("1280x720", 30, 4)
        + ["-f", "lavfi", "-i", "sine=frequency=330:sample_rate=44100:duration=4"]
        + _H264
        + ["-ac", "1", "-c:a", "aac", "-b:a", "64k"],
    ),
    "h264_noisy": (
        "h264_noisy.mp4",
        _video("1280x720", 30, 4)
        + ["-f", "lavfi", "-i", "anoisesrc=d=4:c=pink:r=48000:a=0.3:seed=7"]
        + _H264
        + _AAC,
    ),
    "h264_2s": ("h264_2s.mp4", _video("1280x720", 30, 2) + _audio(2) + _H264 + _AAC),
    "av_late_500": (  # audio starts 500 ms after the video
        "av_late_500.mp4",
        _video("1280x720", 30, 4) + ["-itsoffset", "0.5"] + _audio(4) + _H264 + _AAC,
    ),
    "av_early_500": (  # audio starts 500 ms before the video
        "av_early_500.mp4",
        _video("1280x720", 30, 4) + ["-itsoffset", "-0.5"] + _audio(4) + _H264 + _AAC,
    ),
}
TAGS: dict[str, list[str]] = {
    "hevc_iphone": ["hevc", "mov"],
    "hevc_rot90": ["hevc", "mov", "rotation"],
    "h264_vertical": ["portrait"],
    "h264_noaudio": ["no_audio"],
    "h264_quiet": ["quiet_audio"],
    "vp9_opus_webm": ["webm", "vp9"],
    "mpeg4_avi": ["avi"],
    "h264_vfr": ["vfr"],
    "h264_4x3": ["4:3"],
    "prores_lite": ["prores", "mov", "pcm_audio"],
    "h264_mkv": ["mkv"],
    "h264_mono_44k": ["mono", "44k1"],
    "h264_noisy": ["noisy_audio"],
    "av_late_500": ["av_offset"],
    "av_early_500": ["av_offset"],
    "h264_rot270": ["rotation", "portrait"],
}
KNOWN_OFFSET_MS: dict[str, float] = {"av_late_500": 500.0, "av_early_500": -500.0}

# Derived clip: remux hevc_iphone with display rotation 90 (iPhone portrait-style metadata).
# Verified on FFmpeg 9: `-display_rotation` is an input option; ffprobe then reports rotation 90.
DERIVED: dict[str, tuple[str, str, list[str]]] = {
    "hevc_rot90": ("hevc_rot90.mov", "hevc_iphone", ["-display_rotation", "90"]),
    # Portrait-style H.264 with display-matrix rotation 270 clockwise (FFmpeg `-display_rotation 90`).
    "h264_rot270": ("h264_rot270.mp4", "h264_aac_1080p", ["-display_rotation", "90"]),
}


def _ffmpeg(args: list[str], out: Path) -> None:
    argv = [
        config.FFMPEG_BIN,
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-y",
        *args,
        *_STABLE,
        str(out),
    ]
    subprocess.run(argv, shell=False, check=True, capture_output=True)


def _record(clip_id: str, path: Path) -> ClipRecord:
    return ClipRecord(
        id=clip_id,
        file=path.name,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        licence=LICENCE,
        source="synthetic",
        probe=probe(path),
        tags=TAGS.get(clip_id, []),
        known_offset_ms=KNOWN_OFFSET_MS.get(clip_id),
    )


def make_corpus(out_dir: Path, ids: set[str] | None = None) -> list[ClipRecord]:
    """Generate all clips, or only `ids` (plus the sources derived clips need)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    derived = {k: v for k, v in DERIVED.items() if ids is None or k in ids}
    base = {k for k in RECIPES if ids is None or k in ids} | {src for _, src, _ in derived.values()}
    records = []
    for clip_id, (name, args) in RECIPES.items():
        if clip_id in base:
            _ffmpeg(args, out_dir / name)
            if ids is None or clip_id in ids:
                records.append(_record(clip_id, out_dir / name))
    for clip_id, (name, src_id, input_opts) in derived.items():
        src = out_dir / RECIPES[src_id][0]
        _ffmpeg([*input_opts, "-i", str(src), "-c", "copy"], out_dir / name)
        records.append(_record(clip_id, out_dir / name))
    return records


def ensure_corpus(out_dir: Path, ids: set[str] | None = None) -> dict[str, Path]:
    """Clip paths by id (all clips, or only `ids`), generating them if any is missing (e.g. a fresh
    git clone: the manifest is tracked, the media is not). Never rewrites the tracked manifest."""
    wanted = ids if ids is not None else set(RECIPES) | set(DERIVED)
    manifest = out_dir / "manifest.json"
    if manifest.exists():
        paths = {r["id"]: out_dir / r["file"] for r in json.loads(manifest.read_text())}
        if wanted <= set(paths) and all(paths[i].is_file() for i in wanted):
            return {i: paths[i] for i in wanted}
    return {r["id"]: out_dir / r["file"] for r in make_corpus(out_dir, ids)}


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else config.CORPUS_DIR
    records = make_corpus(out_dir)
    (out_dir / "manifest.json").write_text(json.dumps(records, indent=2) + "\n")
    print(f"wrote {len(records)} clips to {out_dir}")


if __name__ == "__main__":
    main()
