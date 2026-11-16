"""Net rotation of an output relative to its input, measured from picture content (checker v1.2).

Convention (same as spec.schema.json `video.rotation`): CLOCKWISE degrees the *displayed* picture of the
output is turned relative to the displayed picture of the input, however it was done (display-matrix
metadata or re-encoded pixels). FFmpeg applies display-matrix rotation when decoding, so a thumbnail of
either file is already what a viewer sees.

Method: first frame of each file -> 32x32 grey thumbnail; turn the input's thumbnail by 0/90/180/270
degrees clockwise and pick the candidate closest (mean absolute difference) to the output's. Squashing to a
square commutes with rotation, so aspect ratios do not matter. Ambiguous or unreadable -> None (the field
then fails: fail closed). shortcut: first frame only, so a heavily trimmed output whose first frame differs
from the input's first frame can mis-measure; the F5 tasks keep the whole clip.
"""

import subprocess
from pathlib import Path

from training import config

Thumb = list[list[int]]


def thumbnail(path: Path, size: int = config.ORIENTATION_THUMB) -> Thumb | None:
    argv = [
        config.FFMPEG_BIN, "-hide_banner", "-nostdin", "-v", "error", "-i", str(path),
        "-frames:v", "1", "-vf", f"scale={size}:{size}:flags=area,format=gray",
        "-f", "rawvideo", "-",
    ]  # fmt: skip
    try:
        raw = subprocess.run(
            argv, shell=False, capture_output=True, timeout=config.RUN_TIMEOUT_S
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    if len(raw) != size * size:
        return None
    return [list(raw[r * size : (r + 1) * size]) for r in range(size)]


def rotate_cw(m: Thumb, degrees: int) -> Thumb:
    n = len(m)
    if degrees == 0:
        return m
    if degrees == 90:  # clockwise: new[y][x] = old[n-1-x][y]
        return [[m[n - 1 - x][y] for x in range(n)] for y in range(n)]
    if degrees == 180:
        return [[m[n - 1 - y][n - 1 - x] for x in range(n)] for y in range(n)]
    if degrees == 270:  # counterclockwise 90
        return [[m[x][n - 1 - y] for x in range(n)] for y in range(n)]
    raise ValueError(f"rotation must be 0/90/180/270, got {degrees}")


def _mad(a: Thumb, b: Thumb) -> float:
    n = len(a)
    return sum(abs(a[y][x] - b[y][x]) for y in range(n) for x in range(n)) / (n * n)


def net_rotation_cw_from_thumbs(inp: Thumb, out: Thumb) -> int | None:
    scores = sorted((_mad(rotate_cw(inp, d), out), d) for d in (0, 90, 180, 270))
    (best, degrees), (second, _) = scores[0], scores[1]
    if best > config.ORIENTATION_MAX_RATIO * second or second - best < config.ORIENTATION_MIN_GAP:
        return None
    return degrees


def net_rotation_cw(input_path: Path, output_path: Path) -> int | None:
    a, b = thumbnail(input_path), thumbnail(output_path)
    return None if a is None or b is None else net_rotation_cw_from_thumbs(a, b)
