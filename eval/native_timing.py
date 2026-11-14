"""Native side of the browser-vs-native speed comparison (PHASES Phase 0). Runs the same chores the
browser spike times (packages/protocol/conformance/timing-chores.json) through the validated executor.

uv run python -m eval.native_timing reports/<date>-phase-0/native-timing.json
"""

import json
import subprocess
import sys
import time
from pathlib import Path

from eval.run_baseline import _hardware, load_corpus
from training import config
from training.env.executor import execute


def time_chores(
    corpus: dict[str, Path], out: Path, jobs_root: Path = config.JOBS_DIR / "native-timing"
) -> list[dict]:
    if out.exists():
        raise FileExistsError(out)
    chores = json.loads((config.PROTOCOL_DIR / "conformance" / "timing-chores.json").read_text())
    rows = []
    for c in chores:
        target = jobs_root / c["name"] / c["output"]
        target.parent.mkdir(parents=True, exist_ok=True)
        run = {"action": "run", "args": c["args"], "inputs": ["clip"], "outputs": ["out1"]}
        t0 = time.perf_counter()
        r = execute(run, input_paths={"clip": corpus[c["input"]]}, output_paths={"out1": target})
        rows.append(
            {
                "name": c["name"],
                "family": c["family"],
                "ok": r.ok,
                "seconds": round(time.perf_counter() - t0, 3),
            }
        )
    version = subprocess.run(
        [config.FFMPEG_BIN, "-version"], shell=False, capture_output=True, text=True
    ).stdout
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"ffmpeg_version": version.splitlines()[0], "hardware": _hardware(), "chores": rows},
            indent=2,
        )
        + "\n"
    )
    return rows


if __name__ == "__main__":
    print(json.dumps(time_chores(load_corpus(), Path(sys.argv[1])), indent=2))
