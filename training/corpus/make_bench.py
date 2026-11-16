"""Bench input clips for the Phase 2 browser bench (T7): iPhone-style HEVC at 1080p and 4K, plus two
H.264 clips sized to ~100 MB and ~500 MB. Synthetic (testsrc2 + sine), licence CC0, gitignored under data/bench.

  uv run python -m training.corpus.make_bench data/bench          # full size (60 s each; takes a few minutes)

The two H.264 clips use CBR with HRD padding so file size tracks bitrate x duration even though the
synthetic picture compresses extremely well; the same size targets scale down for tests via duration_s.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from training import config
from training.env.probe import probe

# name -> (filename, video size, video args)
_HEVC = [
    "-c:v",
    "libx265",
    "-preset",
    "ultrafast",
    "-tag:v",
    "hvc1",
    "-x265-params",
    "log-level=error",
]


def _cbr(mbit: float) -> list[str]:
    rate = f"{int(mbit * 1000)}k"
    return [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-b:v",
        rate,
        "-minrate",
        rate,
        "-maxrate",
        rate,
        "-bufsize",
        f"{int(mbit * 2000)}k",
        "-x264-params",
        "nal-hrd=cbr:force-cfr=1",
    ]


def _bench_recipes(duration_s: float) -> dict[str, tuple[str, str, list[str]]]:
    mbit = lambda mb: mb * 8 / 60  # noqa: E731  (a "<N> MB / 60 s" clip's bitrate in Mbit/s)
    return {
        "hevc_1080p_60s": ("hevc_1080p_60s.mov", "1920x1080", _HEVC + ["-b:v", "12M"]),
        "hevc_4k_60s": ("hevc_4k_60s.mov", "3840x2160", _HEVC + ["-b:v", "30M"]),
        "h264_100mb_60s": ("h264_100mb_60s.mp4", "1920x1080", _cbr(mbit(100))),
        "h264_500mb_60s": ("h264_500mb_60s.mp4", "1920x1080", _cbr(mbit(500))),
    }


BENCH_CLIPS = tuple(_bench_recipes(60))


def make_bench(out_dir: Path, duration_s: float = 60.0) -> dict[str, dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict] = {}
    for clip_id, (name, size, vargs) in _bench_recipes(duration_s).items():
        path = out_dir / name
        argv = [
            config.FFMPEG_BIN,
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={size}:rate=30:duration={duration_s}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=48000:duration={duration_s}",
            *vargs,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-fflags",
            "+bitexact",
            "-map_metadata",
            "-1",
            str(path),
        ]
        subprocess.run(argv, shell=False, check=True, capture_output=True)
        p = probe(path)
        v = next(s for s in p["streams"] if s["type"] == "video")
        records[clip_id] = {
            "file": name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "codec": v["codec"],
            "width": v["width"],
            "height": v["height"],
            "duration_s": p["duration_s"],
            "licence": "CC0-1.0 (synthetic, generated)",
        }
    return records


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else config.DATA_DIR / "bench"
    recs = make_bench(out)
    (out / "manifest.json").write_text(json.dumps(recs, indent=2) + "\n")
    for k, r in recs.items():
        print(
            f"{k}: {r['bytes'] / 1e6:.0f} MB  {r['codec']} {r['width']}x{r['height']}  {r['duration_s']:.1f}s"
        )


if __name__ == "__main__":
    main()
