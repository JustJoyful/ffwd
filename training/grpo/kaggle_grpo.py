"""Create, run and watch the GRPO runs on Kaggle through the Kaggle API (no web-UI notebook).

  uv run python -m training.grpo.kaggle_grpo push --mode probe            # are the Secrets readable? (no GPU, ~1 minute)
  uv run python -m training.grpo.kaggle_grpo push --mode smoke            # 2-step pipeline test, Hub push per step
  uv run python -m training.grpo.kaggle_grpo push --mode control --approved
  uv run python -m training.grpo.kaggle_grpo push --mode main --approved --control-passed --steps 100
  uv run python -m training.grpo.kaggle_grpo status | wait [--timeout-min N] | fetch --out DIR

The pushed script is training/grpo/kaggle_remote.py with a PARAMS line prepended. HF_TOKEN and GITHUB_TOKEN are read inside
the kernel from its Secrets. Tested 20 Nov 2026: Secrets are visible only to runs started from the web UI (Run All in the
editor), NOT to runs started through the API, even after the owner attached them and saved a committed version. So `push`
saves the new version WITHOUT running it (`--no-run`); the owner opens the kernel and presses Run All; this tool then
watches (`status`/`wait`) and fetches the log. No token is ever in the pushed code.
Gates (owner decisions): control needs --approved; main needs --approved and --control-passed; both need the pool file to be
committed on origin/main (the kernel clones it from there).
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from training import config
from training.grpo.kaggle_kernel import kaggle

SLUG = "justjoyful/ffmpeg-agent-grpo-auto"
REMOTE = Path(__file__).with_name("kaggle_remote.py")
POOL_IDS = "reports/2026-11-20-grpo-pool/pool-ids.txt"
T18_TABLE = "reports/2026-11-20-t18-pass-rates/taskfilter/pass_rates.json"
HUB = "JustJoyful/ffmpeg-agent-ckpt"
MODES = ("probe", "smoke", "control", "main")


class GateError(SystemExit):
    pass


def params(mode: str, *, steps: int | None = None, resume: bool = False) -> dict:
    p = {
        "mode": mode, "resume": resume, "repo": "JustJoyful/ffmpeg-agent", "branch": "main",
        "m1_repo": "JustJoyful/ffmpeg-agent-m1-0.6b", "corpus_repo": config.CORPUS_HUB_REPO,
        "num_generations": 8, "prompts_per_step": 8, "max_new_tokens": 256,
        "max_runs": config.MAX_RUNS_PER_JOB, "max_gpu_hours": config.GRPO_STOP_RULES["max_gpu_hours"],
        "save_steps": 10, "steps": steps or 100, "pool_ids": None, "pass_rates": T18_TABLE,
        "extra_train": [], "shuffle_seed": None, "hub_repo": f"{HUB}-grpo",
    }  # fmt: skip
    if mode == "smoke":
        p |= {"steps": 2, "save_steps": 1, "num_generations": 2, "prompts_per_step": 1,
              "max_new_tokens": 128, "max_runs": 2, "hub_repo": f"{HUB}-smoke-kaggle"}  # fmt: skip
    elif mode in ("control", "main"):
        p |= {"pool_ids": POOL_IDS, "extra_train": ["hard-v1"]}
        if mode == "control":
            p |= {"steps": steps or 30, "shuffle_seed": 20261115, "hub_repo": f"{HUB}-grpo-control"}
    return p


def check_gates(mode: str, *, approved: bool, control_passed: bool, pool_on_origin: bool) -> None:
    if mode in ("control", "main") and not approved:
        raise GateError("GRPO is not approved (gate G3): the owner must pass --approved")
    if mode == "main" and not control_passed:
        raise GateError(
            "the shuffled-reward control has not passed: the owner must pass --control-passed"
        )
    if mode in ("control", "main") and not pool_on_origin:
        raise GateError(f"{POOL_IDS} is not on origin/main: build the pool, commit and push first")


def script(p: dict) -> str:
    return (
        f"PARAMS = {p!r}\n" + REMOTE.read_text()
    )  # a Python literal (json would write false/null)


def pool_on_origin() -> bool:
    subprocess.run(["git", "fetch", "-q", "origin"], check=False)
    return (
        subprocess.run(
            ["git", "cat-file", "-e", f"origin/main:{POOL_IDS}"], capture_output=True
        ).returncode
        == 0
    )


def push(p: dict, run: bool = False) -> int:
    """New kernel version. By default it is saved WITHOUT running (`--no-run`, Quick Save): an API-started run cannot read
    the kernel's Secrets (tested 20 Nov 2026, even after a UI commit), so it would only fail at the first line. The owner
    opens the kernel in the web UI and presses Run All, which does get the Secrets."""
    gpu = p["mode"] != "probe"
    with tempfile.TemporaryDirectory(prefix="kernel-") as d:
        (Path(d) / "run.py").write_text(script(p))
        (Path(d) / "kernel-metadata.json").write_text(
            json.dumps(
                {"id": SLUG, "title": "ffmpeg-agent-grpo-auto", "code_file": "run.py", "language": "python",
                 "kernel_type": "script", "is_private": True, "enable_gpu": gpu, "enable_internet": True}  # fmt: skip
            )
        )
        args = ["kernels", "push", "-p", d] + (["--accelerator", "NvidiaTeslaT4"] if gpu else [])
        args += [] if run else ["--no-run"]
        r = kaggle(*args, check=False)
    print(r.stdout, r.stderr)
    return r.returncode


def wait(timeout_min: float, poll_s: int = 30) -> str:
    end, status = time.time() + 60 * timeout_min, ""
    while time.time() < end:
        status = kaggle("kernels", "status", SLUG, check=False).stdout.strip()
        print(time.strftime("%H:%M:%S"), status, flush=True)
        if any(s in status.upper() for s in ("COMPLETE", "ERROR", "CANCEL")):
            break
        time.sleep(poll_s)
    return status


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pu = sub.add_parser("push")
    pu.add_argument("--mode", choices=MODES, required=True)
    pu.add_argument("--steps", type=int)
    pu.add_argument("--resume", action="store_true")
    pu.add_argument(
        "--run",
        action="store_true",
        help="also start the run from the API (no Secrets there: it fails)",
    )
    pu.add_argument(
        "--approved", action="store_true", help="owner's G3 go-ahead (control and main)"
    )
    pu.add_argument(
        "--control-passed",
        action="store_true",
        help="owner: the control was evaluated and passed (main)",
    )
    sub.add_parser("status")
    w = sub.add_parser("wait")
    w.add_argument("--timeout-min", type=float, default=60)
    f = sub.add_parser("fetch")
    f.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == "push":
        check_gates(a.mode, approved=a.approved, control_passed=a.control_passed,
                    pool_on_origin=pool_on_origin() if a.mode in ("control", "main") else True)  # fmt: skip
        sys.exit(push(params(a.mode, steps=a.steps, resume=a.resume), run=a.run))
    if a.cmd == "status":
        print(kaggle("kernels", "status", SLUG, check=False).stdout)
    elif a.cmd == "wait":
        print(wait(a.timeout_min))
    else:
        a.out.mkdir(parents=True, exist_ok=True)
        r = kaggle("kernels", "output", SLUG, "-p", str(a.out), check=False)
        print(r.stdout, r.stderr)


if __name__ == "__main__":
    main()
