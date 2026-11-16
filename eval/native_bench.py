"""Native-FFmpeg timings for the Phase 2 bench jobs (T7): the same commands the browser bench runs
(packages/protocol/conformance/bench-jobs.json), through the validated executor.

uv run python -m eval.native_bench data/bench reports/<date>-phase0-followups/bench/native-<machine>.json
"""

import json
import subprocess
import sys
import time
from pathlib import Path

from eval.run_baseline import _hardware
from training import config
from training.env.executor import execute

JOBS = [  # (record name as in the browser bench, clip id, job key)
    ("bench_hevc_1080p_60s_to_h264", "hevc_1080p_60s", "hevcToH264"),
    ("bench_f4_480p_60s_input100mb", "h264_100mb_60s", "f4Scale480"),
    ("bench_hevc_4k_60s_to_h264", "hevc_4k_60s", "hevcToH264"),
    ("bench_f4_480p_60s_input500mb", "h264_500mb_60s", "f4Scale480"),
]


def time_bench(bench_dir: Path, out: Path) -> list[dict]:
    if out.exists():
        raise FileExistsError(out)
    manifest = json.loads((bench_dir / "manifest.json").read_text())
    args = json.loads((config.PROTOCOL_DIR / "conformance" / "bench-jobs.json").read_text())
    rows = []
    for name, clip, key in JOBS:
        src, dst = bench_dir / manifest[clip]["file"], bench_dir / f"native_out_{clip}.mp4"
        t0 = time.perf_counter()
        r = execute(
            {"action": "run", "args": args[key], "inputs": ["clip"], "outputs": ["out1"]},
            input_paths={"clip": src},
            output_paths={"out1": dst},
            timeout_s=3600,
        )
        rows.append(
            {
                "name": name,
                "ok": r.ok,
                "seconds": round(time.perf_counter() - t0, 2),
                "input_bytes": src.stat().st_size,
                "output_bytes": dst.stat().st_size if dst.exists() else 0,
            }
        )
        dst.unlink(missing_ok=True)
    version = subprocess.run(
        [config.FFMPEG_BIN, "-version"], shell=False, capture_output=True, text=True
    ).stdout.splitlines()[0]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"ffmpeg_version": version, "hardware": _hardware(), "jobs": rows}, indent=2)
        + "\n"
    )
    return rows


if __name__ == "__main__":
    print(json.dumps(time_bench(Path(sys.argv[1]), Path(sys.argv[2])), indent=2))
