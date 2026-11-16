"""Which FFmpeg is on PATH (or at config.FFMPEG_BIN). Part of the verification-cache key and, once D-024's pinned
build is installed, of the fail-closed pin check."""

import functools
import re
import subprocess

from training import config


@functools.cache
def ffmpeg_version(binary: str = config.FFMPEG_BIN) -> str:
    """'5.1.1', '9.0.2', 'n9.0.2' -> '9.0.2'; git builds return their raw token."""
    out = subprocess.run([binary, "-version"], capture_output=True, text=True, check=True).stdout
    m = re.match(r"ffmpeg version (\S+)", out)
    if m is None:
        raise RuntimeError(f"cannot parse `{binary} -version`: {out[:80]!r}")
    return m.group(1).removeprefix("n")
