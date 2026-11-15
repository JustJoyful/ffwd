"""Run one validated `run` action with FFmpeg (RULES §1, ARCH §3.5).

Order: validate → substitute harness-owned paths for {in:id}/{out:id} → argument-list subprocess
(never a shell) with timeout → enforce output size cap. Any failure deletes declared outputs.
"""

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from training import config
from training.env.validator import validate_run


@dataclass
class RunResult:
    ok: bool
    rejected: str | None = None
    returncode: int | None = None
    timed_out: bool = False
    stderr_tail: str = ""
    outputs: dict[str, Path] = field(default_factory=dict)


def output_path_for(job_dir: Path, out_spec: dict) -> Path:
    """Harness-chosen output path. Image sequences get their own dir and a %04d pattern."""
    out = job_dir / "out"
    if out_spec["kind"] == "image_sequence":
        fmt = (out_spec.get("frames") or {}).get("format") or "png"
        target = out / out_spec["id"] / f"%04d.{fmt}"
    else:
        target = out / f"{out_spec['id']}.{out_spec.get('container') or 'mp4'}"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _artifact(path: Path) -> Path:
    """The thing that exists on disk for an output: the file, or the dir for a %04d pattern."""
    return path.parent if "%" in path.name else path


def _size(p: Path) -> int:
    if p.is_dir():
        return sum(f.stat().st_size for f in p.iterdir() if f.is_file())
    return p.stat().st_size if p.exists() else 0


def _delete(paths: dict[str, Path]) -> None:
    for p in map(_artifact, paths.values()):
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def _tail(b: bytes | str | None) -> str:
    text = b.decode(errors="replace") if isinstance(b, bytes) else (b or "")
    return text[-config.STDERR_TAIL_CHARS :]


def execute(
    run: dict,
    *,
    input_paths: dict[str, Path],
    output_paths: dict[str, Path],
    timeout_s: int = config.RUN_TIMEOUT_S,
    max_output_bytes: int = config.MAX_OUTPUT_BYTES,
) -> RunResult:
    v = validate_run(
        run["args"],
        run["inputs"],
        run["outputs"],
        known_inputs=set(input_paths),
        known_outputs=set(output_paths),
    )
    if not v.ok:
        return RunResult(ok=False, rejected=v.reason, stderr_tail=f"rejected: {v.reason}")

    subst = {f"{{in:{k}}}": str(p) for k, p in input_paths.items()}
    subst |= {f"{{out:{k}}}": str(p) for k, p in output_paths.items()}
    # No thread cap here: the ffmpeg.wasm deadlock (spikes/browser/src/harness-args.ts) does not affect
    # native FFmpeg; Phase 0 native F4 ran in 0.68 s with default threading.
    # -y is safe: every output path is a fresh, harness-owned file inside the job dir.
    argv = [
        config.FFMPEG_BIN,
        "-hide_banner",
        "-nostdin",
        "-y",
        *(subst.get(a, a) for a in run["args"]),
    ]
    declared = {k: output_paths[k] for k in run["outputs"]}
    try:
        proc = subprocess.run(argv, shell=False, capture_output=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        _delete(declared)
        return RunResult(ok=False, timed_out=True, stderr_tail=_tail(e.stderr) + "\n[timed out]")

    tail = _tail(proc.stderr)
    if proc.returncode != 0:
        _delete(declared)
        return RunResult(ok=False, returncode=proc.returncode, stderr_tail=tail)
    sizes = {k: _size(_artifact(p)) for k, p in declared.items()}
    if any(s == 0 for s in sizes.values()):
        _delete(declared)
        return RunResult(
            ok=False,
            returncode=0,
            stderr_tail=(tail + "\n[missing or empty output]")[-config.STDERR_TAIL_CHARS :],
        )
    # shortcut: cap checked after exit, so a run can briefly exceed it on disk; add FFmpeg -fs
    # per output if the helper (Phase 3) runs on user disks.
    if sum(sizes.values()) > max_output_bytes:
        _delete(declared)
        return RunResult(
            ok=False,
            returncode=0,
            stderr_tail=f"[output exceeds size cap of {max_output_bytes} bytes]",
        )
    return RunResult(
        ok=True,
        returncode=0,
        stderr_tail=tail,
        outputs={k: _artifact(p) for k, p in declared.items()},
    )
