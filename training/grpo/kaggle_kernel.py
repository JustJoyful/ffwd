"""Run the kill-and-resume test on Kaggle from this machine (replaces the manual notebook clicking).

  uv run python -m training.grpo.kaggle_kernel push --mode train    # session 1: dies after checkpoint 4
  uv run python -m training.grpo.kaggle_kernel status
  uv run python -m training.grpo.kaggle_kernel fetch                # downloads log into <out>
  uv run python -m training.grpo.kaggle_kernel push --mode resume   # session 2: a fresh machine, resumes

Each push is a separate Kaggle run = a fresh VM with an empty /kaggle/working, which is exactly the
"session killed, checkpoints gone" case. The kernel needs the HF_TOKEN and GITHUB_TOKEN secrets attached
(one-time, in the web UI); tokens never appear in the pushed code.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SLUG = "justjoyful/ffmpeg-agent-resume-auto"
HF_REPO = "JustJoyful/ffmpeg-agent-ckpt"
STEPS, KILL_AFTER = 8, 4
KAGGLE = ["uvx", "--with", "six", "kaggle"]  # shortcut: ad-hoc CLI; pin a version if it breaks

SCRIPT = """
import os, subprocess, sys
from kaggle_secrets import UserSecretsClient

MODE = "{mode}"
s = UserSecretsClient()
os.environ["HF_TOKEN"] = s.get_secret("HF_TOKEN")
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["TRL_EXPERIMENTAL_SILENCE"] = "1"
gh = s.get_secret("GITHUB_TOKEN")
dest = "/kaggle/working/ffmpeg-agent"
subprocess.run(["git", "clone", "--branch", "main", f"https://x-access-token:{{gh}}@github.com/JustJoyful/ffmpeg-agent.git", dest], check=True)
subprocess.run(["git", "-C", dest, "remote", "set-url", "origin", "https://github.com/JustJoyful/ffmpeg-agent.git"], check=True)
del gh

def sh(cmd, ok=(0,)):
    print("$", cmd, flush=True)
    rc = subprocess.run(cmd, shell=True, cwd=dest).returncode
    print("exit code:", rc, flush=True)
    if rc not in ok:
        sys.exit(rc)
    return rc

sh("git log --oneline -1; nvidia-smi -L")
sh("curl -LsSf https://astral.sh/uv/install.sh | sh")
sh("uv sync --group train")
sh("uv run python -m training.env.ffmpeg_pin install")  # the ONE pinned FFmpeg (D-024), never apt's
sh("uv run --group train python -c \\"import torch; assert torch.cuda.is_available(); print('cuda ok')\\"")
train = "uv run --group train python -m training.grpo.toy_spike --model Qwen/Qwen3-0.6B --steps {steps} --save-steps 2 --hub-repo {hub} --ckpt-dir /kaggle/working/ckpt"
if MODE == "train":
    sh(train + " --crash-after {kill}", ok=(42,))  # 42 = the intended kill right after the push
    print("SESSION 1 DONE: killed after checkpoint {kill} was pushed")
else:
    sh(train + " --resume")
    sh("uv run python -m training.grpo.verify_resume --ckpt-dir /kaggle/working/ckpt --max-steps {steps} --resumed-after {kill}")
    sh("cat /kaggle/working/ckpt/toy_metrics.jsonl")
"""


def kaggle(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run([*KAGGLE, *args], text=True, capture_output=True, check=check)


def push(mode: str) -> None:
    with tempfile.TemporaryDirectory(prefix="kernel-") as d:
        (Path(d) / "run.py").write_text(
            SCRIPT.format(mode=mode, steps=STEPS, kill=KILL_AFTER, hub=HF_REPO)
        )
        (Path(d) / "kernel-metadata.json").write_text(
            json.dumps(
                {
                    "id": SLUG,
                    "title": "ffmpeg-agent-resume-auto",
                    "code_file": "run.py",
                    "language": "python",
                    "kernel_type": "script",
                    "is_private": True,
                    "enable_gpu": True,
                    "enable_internet": True,
                }
            )
        )
        r = kaggle("kernels", "push", "-p", d, "--accelerator", "NvidiaTeslaT4", check=False)
    print(r.stdout, r.stderr)
    sys.exit(r.returncode)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("push").add_argument("--mode", choices=["train", "resume"], required=True)
    sub.add_parser("status")
    f = sub.add_parser("fetch")
    f.add_argument("--out", type=Path, default=Path("/tmp/kaggle-out"))
    a = ap.parse_args()
    if a.cmd == "push":
        push(a.mode)
    elif a.cmd == "status":
        print(kaggle("kernels", "status", SLUG, check=False).stdout)
    else:
        a.out.mkdir(parents=True, exist_ok=True)
        r = kaggle("kernels", "output", SLUG, "-p", str(a.out), check=False)
        print(r.stdout, r.stderr)


if __name__ == "__main__":
    main()
