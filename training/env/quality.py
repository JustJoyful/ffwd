"""Picture-quality measurement for size-target outputs (checker v1.1; ARCH §7.4 reward-hacking guards).

Without it, "under 2 MB" is satisfied by a blank or tiny video. SSIM/PSNR of the candidate against the
input, both sampled at QUALITY_SAMPLE_FPS and scaled to the input's size. Only meaningful when the output
keeps the input's timeline and framing; the checker applies the default floor only then (see
checker._quality_applies). Unmeasurable -> None (the field fails: fail closed).
"""

import re
import subprocess
from pathlib import Path

from training import config

_SSIM = re.compile(r"SSIM .*? All:([\d.]+)")
_PSNR = re.compile(r"PSNR .*? average:([\d.inf]+)")


def measure_quality(reference: Path, candidate: Path, width: int, height: int) -> dict | None:
    fps = config.QUALITY_SAMPLE_FPS
    prep = f"fps={fps},scale={width}:{height}:flags=bicubic,format=yuv420p"
    graph = f"[0:v]{prep},split[a1][a2];[1:v]{prep},split[b1][b2];[a1][b1]ssim;[a2][b2]psnr"
    argv = [
        config.FFMPEG_BIN, "-hide_banner", "-nostdin", "-i", str(candidate), "-i", str(reference),
        "-filter_complex", graph, "-f", "null", "-",
    ]  # fmt: skip
    try:
        proc = subprocess.run(argv, shell=False, capture_output=True, timeout=config.RUN_TIMEOUT_S)
    except (subprocess.SubprocessError, OSError):
        return None
    err = proc.stderr.decode(errors="replace")
    ssim, psnr = _SSIM.findall(err), _PSNR.findall(err)
    if not ssim or not psnr:
        return None
    p = psnr[-1]
    return {"ssim": float(ssim[-1]), "psnr_db": 100.0 if p == "inf" else float(p)}
