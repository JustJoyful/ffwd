"""Optional bubblewrap sandbox for FFmpeg runs (RULES §1.6: training rollouts run sandboxed, fail closed).

Inside: no network, own PID namespace, the whole filesystem read-only except the job's output
directories. Modes (config.SANDBOX_DEFAULT, env FFMPEG_AGENT_SANDBOX):
  off      no sandbox (evals on the owner's machine; the validator already rejects protocols/paths)
  auto     use bubblewrap when it works here, else run unsandboxed
  require  FAIL CLOSED: raise SandboxUnavailable instead of running unsandboxed (GRPO rollouts)
Kaggle may forbid user namespaces; there "require" fails loudly and the run must document the limitation
instead of silently falling back.
"""

import shutil
import subprocess
from functools import cache
from pathlib import Path


class SandboxUnavailable(RuntimeError):
    pass


@cache
def _works() -> bool:
    if shutil.which("bwrap") is None:
        return False
    try:
        r = subprocess.run(
            ["bwrap", "--unshare-net", "--unshare-pid", "--ro-bind", "/", "/", "true"],
            shell=False,
            capture_output=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    return r.returncode == 0


def sandbox_prefix(mode: str, writable_dirs: list[Path]) -> list[str]:
    if mode not in ("off", "auto", "require"):
        raise ValueError(f"sandbox mode must be off/auto/require, got {mode!r}")
    if mode == "off":
        return []
    if not _works():
        if mode == "require":
            raise SandboxUnavailable("bubblewrap is missing or user namespaces are disabled")
        return []
    argv = ["bwrap", "--unshare-net", "--unshare-pid", "--die-with-parent", "--ro-bind", "/", "/"]
    argv += ["--dev", "/dev", "--proc", "/proc"]
    for d in sorted({str(p) for p in writable_dirs}):
        argv += ["--bind", d, d]
    return argv
