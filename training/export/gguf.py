"""GGUF export through llama.cpp's own tools (argument lists only, no shell).

Needs a llama.cpp SOURCE checkout for `convert_hf_to_gguf.py` (the release binaries do not ship it) and the
`llama-quantize` binary, pinned to the same release as the server (b12032). Paths come from the environment so no
external code is fetched or executed implicitly:
  LLAMA_CPP_DIR=/path/to/llama.cpp   LLAMA_QUANTIZE=/path/to/llama-quantize
"""

import os
import subprocess
import sys
from pathlib import Path

QUANTS = ("q8_0", "q4_k_m")


class ExportToolsMissing(RuntimeError):
    pass


def convert_argv(model_dir: Path, out_f16: Path, llama_cpp_dir: Path) -> list[str]:
    script = llama_cpp_dir / "convert_hf_to_gguf.py"
    if not script.is_file():
        raise ExportToolsMissing(
            f"{script} not found: set LLAMA_CPP_DIR to a llama.cpp checkout at the server's release"
        )
    return [
        sys.executable,
        str(script),
        str(model_dir),
        "--outfile",
        str(out_f16),
        "--outtype",
        "f16",
    ]


def quantize_argv(src_f16: Path, out: Path, quant: str, quantize_bin: Path) -> list[str]:
    if quant not in QUANTS:
        raise ValueError(f"quant must be one of {QUANTS}")
    return [str(quantize_bin), str(src_f16), str(out), quant.upper()]


def to_gguf(model_dir: Path, out_dir: Path, quants: tuple[str, ...] = QUANTS) -> dict[str, Path]:
    cpp, qbin = os.environ.get("LLAMA_CPP_DIR"), os.environ.get("LLAMA_QUANTIZE")
    if not cpp or not qbin:
        raise ExportToolsMissing("set LLAMA_CPP_DIR and LLAMA_QUANTIZE (see module docstring)")
    out_dir.mkdir(parents=True, exist_ok=True)
    f16 = out_dir / f"{model_dir.name}-f16.gguf"
    subprocess.run(convert_argv(model_dir, f16, Path(cpp)), shell=False, check=True)
    outs = {}
    for q in quants:
        outs[q] = out_dir / f"{model_dir.name}-{q}.gguf"
        subprocess.run(quantize_argv(f16, outs[q], q, Path(qbin)), shell=False, check=True)
    return outs
