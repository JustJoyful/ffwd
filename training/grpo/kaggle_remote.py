"""Runs INSIDE a Kaggle script kernel. training/grpo/kaggle_grpo.py prepends `PARAMS = {...}` and pushes this file.

Modes: probe (are the Secrets readable?), smoke (2 steps), control (shuffled-reward), main. Same steps as
training/grpo/kaggle_main_run.ipynb: partial sparse clone WITHOUT the held-out splits, an assertion that no held-out data is
on the machine, the pinned FFmpeg (sha256 check logged), M1 rebuilt from the Hub adapter, main_run with a Hub push per save,
and an evidence file. Tokens come only from the kernel's Secrets (attached once in the web UI); values are never printed.
"""

import glob
import json
import os
import subprocess
import sys

P = PARAMS  # noqa: F821  (prepended by kaggle_grpo.py)
DEST = "/kaggle/working/ffmpeg-agent"
LOG = "/kaggle/working/run.log"


def sh(cmd: str, cwd: str | None = None, ok: tuple[int, ...] = (0,)) -> int:
    print("$", cmd, flush=True)
    rc = subprocess.run(
        ["bash", "-o", "pipefail", "-c", f"{cmd} 2>&1 | tee -a {LOG}"], cwd=cwd
    ).returncode
    print("exit code:", rc, flush=True)
    if rc not in ok:
        sys.exit(rc)
    return rc


def secret(name: str) -> str | None:
    from kaggle_secrets import UserSecretsClient

    try:
        return UserSecretsClient().get_secret(name)
    except Exception as e:  # noqa: BLE001
        print(f"SECRET {name}: not readable ({type(e).__name__}: {e})", flush=True)
        return None


def assert_no_heldout_data() -> None:
    """No test-* task file or blob and no test-real clip on this machine (D-042)."""
    assert not glob.glob(f"{DEST}/data/tasks/test-*"), "a test split is checked out"
    tree = subprocess.run(
        ["git", "-C", DEST, "ls-tree", "-r", "HEAD", "--name-only"],
        capture_output=True, text=True, check=True,
    ).stdout.split()  # fmt: skip
    test_files = [f for f in tree if f.startswith("data/tasks/test-")]
    assert test_files, "unexpected: the repo lists no test files (wrong branch?)"
    for f in test_files:
        have = subprocess.run(
            ["git", "-C", DEST, "cat-file", "-e", f"HEAD:{f}"],
            env={**os.environ, "GIT_NO_LAZY_FETCH": "1"}, capture_output=True,
        ).returncode == 0  # fmt: skip
        assert not have, f"test blob is on this machine: {f}"
    real = {
        r["id"]
        for r in json.load(open(f"{DEST}/data/corpus/manifest.json"))
        if r.get("role") == "test-real"
    }
    clips = [
        f for f in glob.glob(f"{DEST}/data/corpus/*") if os.path.basename(f).split(".")[0] in real
    ]
    assert not clips, "a test-real clip is on this machine"
    msg = (
        f"ASSERT OK: no test-* task file or blob and no test-real clip on this machine; "
        f"{len(test_files)} test files stay on GitHub only"
    )
    print(msg, flush=True)
    with open(LOG, "a") as f:  # the evidence file greps run.log, so the line must be there too
        f.write(msg + "\n")


def main_run_args() -> str:
    a = (
        f"--init /kaggle/working/m1-merged --ckpt-dir /kaggle/working/{P['mode']} --steps {P['steps']} "
        f"--save-steps {P['save_steps']} --num-generations {P['num_generations']} "
        f"--prompts-per-step {P['prompts_per_step']} --max-new-tokens {P['max_new_tokens']} "
        f"--max-runs {P['max_runs']} --max-gpu-hours {P['max_gpu_hours']} "
        f"--corpus-repo {P['corpus_repo']} --hub-repo {P['hub_repo']}"
    )
    if P["pool_ids"]:
        a += f" --pool-ids {P['pool_ids']}"
    else:
        a += f" --pass-rates {P['pass_rates']} --pass-rates-subset"
    for name in P["extra_train"]:
        a += f" --extra-train {name}"
    if P["shuffle_seed"] is not None:
        a += f" --shuffle-rewards {P['shuffle_seed']}"
    return a + (" --resume" if P["resume"] else "")


def main() -> None:
    hf, gh = secret("HF_TOKEN"), secret("GITHUB_TOKEN")
    print(
        "SECRET HF_TOKEN:",
        "ok" if hf else "MISSING",
        "| GITHUB_TOKEN:",
        "ok" if gh else "MISSING",
        flush=True,
    )
    if P["mode"] == "probe":
        sys.exit(0 if hf and gh else 3)
    if not (hf and gh):
        sys.exit(
            "Secrets are not attached to this kernel: attach HF_TOKEN and GITHUB_TOKEN once in the Kaggle web UI"
        )
    os.environ.update(HF_TOKEN=hf, CUDA_VISIBLE_DEVICES="0", TRL_EXPERIMENTAL_SILENCE="1")
    # the first control run died of an OOM with 4.2 GiB "reserved but unallocated" (fragmentation); PyTorch's own advice
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    if not os.path.exists(DEST):
        url = f"https://x-access-token:{gh}@github.com/{P['repo']}.git"
        # partial + sparse clone: the held-out splits are neither checked out nor downloaded; the token stays in the URL until
        # the checkout is done, then it is removed from .git/config
        sh(f"git clone --no-checkout --filter=blob:none --branch {P['branch']} {url} {DEST}")
        sh(f"git -C {DEST} sparse-checkout set --no-cone '/*' '!/data/tasks/test-*/'")
        sh(f"git -C {DEST} checkout {P['branch']}")
        sh(f"git -C {DEST} remote set-url origin https://github.com/{P['repo']}.git")
    del gh
    sh("git log --oneline -1; nvidia-smi -L", cwd=DEST)
    assert_no_heldout_data()
    sh("curl -LsSf https://astral.sh/uv/install.sh | sh")
    os.environ["PATH"] = f"{os.path.expanduser('~')}/.local/bin:{os.environ['PATH']}"
    sh("uv sync --group train", cwd=DEST)
    sh(
        "uv run python -m training.env.ffmpeg_pin install", cwd=DEST
    )  # the ONE pinned FFmpeg (D-024): logs the sha256 check
    sh("uv run python -m training.env.ffmpeg_pin check", cwd=DEST)
    sh(
        "uv run --group train python -c \"import torch; assert torch.cuda.is_available(); print('cuda ok', torch.cuda.get_device_name(0))\"",
        cwd=DEST,
    )
    if not os.path.exists("/kaggle/working/m1-merged"):
        sh(
            'uv run --group train python -c "from huggingface_hub import snapshot_download as s; '
            f"s('{P['m1_repo']}', allow_patterns=['adapter/*'], local_dir='/kaggle/working/m1-hub')\"",
            cwd=DEST,
        )
        sh(
            "uv run --group train python -m training.export.merge --adapter /kaggle/working/m1-hub/adapter --out /kaggle/working/m1-merged",
            cwd=DEST,
        )
    sh(f"uv run --group train python -m training.grpo.main_run {main_run_args()}", cwd=DEST)
    sh(
        f'grep -E "ffmpeg pin: sha256|ffmpeg pinned build verified|ASSERT OK|pushed to" {LOG} | tee /kaggle/working/evidence.txt',
        ok=(0, 1),
    )
    print(f"RUN DONE: mode={P['mode']}", flush=True)


if (
    __name__ == "__main__"
):  # a Kaggle script kernel runs as __main__; tests exec the source with another name
    main()
