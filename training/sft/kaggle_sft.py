"""Run the M1 SFT on Kaggle (T4, free) from this machine, without Kaggle secrets or any token in pushed code.

API-pushed kernels cannot read Kaggle secrets (the 16-17 Nov kill-and-resume attempts, reports/PHASE1-STATUS.md), so this
path needs none: the code at ONE git commit plus the SFT examples go up as a PRIVATE Kaggle dataset, the kernel trains
from /kaggle/input and leaves the LoRA adapter in /kaggle/working, and `fetch` downloads that kernel output.
Batch 2 x accumulation 8 (= the config's effective 16): the loss upcasts a (batch x ~2-3k tokens x 152k vocab) logits tensor
to fp32, which with batch 4 is ~7 GB on a 15 GB T4. Checkpoints (adapter + optimizer + trainer state) are written every `--save-steps`, so the Trainer resumes inside a
session; there is no off-box sync here because that would need an HF token on the box (D-022 covers the token path;
this run is ~1-2 h against a 12 h limit). The base model is public.

  uv run python -m training.sft.kaggle_sft package --data data/sft/m1 --out /tmp/sft-pkg [--commit HEAD]
  uv run python -m training.sft.kaggle_sft push --pkg /tmp/sft-pkg --epochs 3
  uv run python -m training.sft.kaggle_sft status
  uv run python -m training.sft.kaggle_sft fetch --out data/sft/m1-kaggle-out
"""

import argparse
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from training import config
from training.grpo.kaggle_kernel import kaggle

OWNER = "justjoyful"
DATASET = f"{OWNER}/ffmpeg-agent-sft-v1"
SLUG = f"{OWNER}/ffmpeg-agent-sft-m1"
CODE_PATHS = (
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    "training",
    "packages/protocol",
)  # what training imports
DATA_FILES = ("examples.jsonl", "val.jsonl", "stats.json")

SCRIPT = """
import os, shutil, subprocess, sys, tarfile

IN = "/kaggle/input/ffmpeg-agent-sft-v1"
dest = "/kaggle/working/ffmpeg-agent"
os.makedirs(dest, exist_ok=True)
with tarfile.open(IN + "/code.tar") as t:
    t.extractall(dest, filter="data")
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

def sh(cmd):
    print("$", cmd, flush=True)
    rc = subprocess.run(cmd, shell=True, cwd=dest).returncode
    print("exit code:", rc, flush=True)
    if rc:
        sys.exit(rc)

sh("cat COMMIT; nvidia-smi -L")
sh("curl -LsSf https://astral.sh/uv/install.sh | sh")
sh("uv sync --group train")
sh("uv run --group train python -c \\"import torch; assert torch.cuda.is_available(); print('cuda ok', torch.__version__)\\"")
out = "/kaggle/working/sft"
sh("uv run --group train python -m training.sft.train --data " + IN + "/examples.jsonl --val " + IN + "/val.jsonl"
   " --ckpt-dir " + out + " --epochs {epochs} --save-steps {save_steps} --per-device-batch 2 --grad-accum 8")
shutil.copytree(out + "/adapter-final", "/kaggle/working/adapter-final")
shutil.copy(IN + "/stats.json", "/kaggle/working/stats.json")
for name in os.listdir(out):  # keep the output small: the adapter is what we need, not optimizer states
    if name.startswith("checkpoint-"):
        shutil.rmtree(os.path.join(out, name))
print("SFT DONE")
"""


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def package(data: Path, out: Path, commit: str = "HEAD") -> Path:
    """Dataset folder: code.tar (the commit's tracked training code, nothing else), COMMIT, the SFT files, metadata."""
    sha = _git("rev-parse", commit)
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "code-src.tar"
    subprocess.run(["git", "archive", "--format=tar", "-o", str(tmp), sha, *CODE_PATHS], check=True)
    with (
        tarfile.open(tmp) as src,
        tarfile.open(out / "code.tar", "w") as dst,
    ):  # add the commit id next to the code
        for m in src.getmembers():
            dst.addfile(m, src.extractfile(m) if m.isfile() else None)
        info = tarfile.TarInfo("COMMIT")
        body = (sha + "\n").encode()
        info.size = len(body)
        dst.addfile(info, fileobj=io.BytesIO(body))
    tmp.unlink()
    for name in DATA_FILES:
        (out / name).write_bytes((data / name).read_bytes())
    (out / "dataset-metadata.json").write_text(
        json.dumps({"id": DATASET, "title": "ffmpeg-agent-sft-v1", "licenses": [{"name": "other"}]})
    )
    return out


def push(pkg: Path, epochs: int, save_steps: int) -> int:
    r = kaggle("datasets", "create", "-p", str(pkg), "--dir-mode", "skip", check=False)
    if r.returncode:  # already exists: push a new version
        r = kaggle(
            "datasets",
            "version",
            "-p",
            str(pkg),
            "-m",
            "sft data/code",
            "--dir-mode",
            "skip",
            check=False,
        )
    print(r.stdout, r.stderr)
    if r.returncode:
        return r.returncode
    with tempfile.TemporaryDirectory(prefix="kernel-") as d:
        (Path(d) / "run.py").write_text(SCRIPT.format(epochs=epochs, save_steps=save_steps))
        (Path(d) / "kernel-metadata.json").write_text(
            json.dumps(
                {
                    "id": SLUG, "title": "ffmpeg-agent-sft-m1", "code_file": "run.py", "language": "python",
                    "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
                    "dataset_sources": [DATASET],
                }
            )
        )  # fmt: skip
        k = kaggle("kernels", "push", "-p", d, "--accelerator", "NvidiaTeslaT4", check=False)
    print(k.stdout, k.stderr)
    return k.returncode


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("package")
    p.add_argument(
        "--data", type=Path, required=True, help="dir with examples.jsonl, val.jsonl, stats.json"
    )
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--commit", default="HEAD")
    q = sub.add_parser("push")
    q.add_argument("--pkg", type=Path, required=True)
    q.add_argument("--epochs", type=int, default=config.SFT_HPARAMS["epochs"])
    q.add_argument("--save-steps", type=int, default=50)
    sub.add_parser("status")
    f = sub.add_parser("fetch")
    f.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == "package":
        print(package(a.data, a.out, a.commit))
    elif a.cmd == "push":
        sys.exit(push(a.pkg, a.epochs, a.save_steps))
    elif a.cmd == "status":
        print(kaggle("kernels", "status", SLUG, check=False).stdout)
    else:
        a.out.mkdir(parents=True, exist_ok=True)
        r = kaggle("kernels", "output", SLUG, "-p", str(a.out), check=False)
        print(r.stdout, r.stderr)


if __name__ == "__main__":
    main()
