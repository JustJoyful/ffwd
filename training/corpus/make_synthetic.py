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
# Derived clip: remux hevc_iphone with display rotation 90 (iPhone portrait-style metadata).
# Verified on FFmpeg 9: `-display_rotation` is an input option; ffprobe then reports rotation 90.
DERIVED: dict[str, tuple[str, str, list[str]]] = {
    "hevc_rot90": ("hevc_rot90.mov", "hevc_iphone", ["-display_rotation", "90"]),
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
    )


def make_corpus(out_dir: Path) -> list[ClipRecord]:
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for clip_id, (name, args) in RECIPES.items():
        _ffmpeg(args, out_dir / name)
        records.append(_record(clip_id, out_dir / name))
    for clip_id, (name, src_id, input_opts) in DERIVED.items():
        src = out_dir / RECIPES[src_id][0]
        _ffmpeg([*input_opts, "-i", str(src), "-c", "copy"], out_dir / name)
        records.append(_record(clip_id, out_dir / name))
    return records


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else config.CORPUS_DIR
    records = make_corpus(out_dir)
    (out_dir / "manifest.json").write_text(json.dumps(records, indent=2) + "\n")
    print(f"wrote {len(records)} clips to {out_dir}")


if __name__ == "__main__":
    main()
