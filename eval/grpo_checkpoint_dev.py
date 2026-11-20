"""Take a GRPO checkpoint from the Hub to a dev judgement (owner, 21 Nov 2026). Dev only; never a test split.

uv run --group train python -m eval.grpo_checkpoint_dev prepare --repo JustJoyful/ffmpeg-agent-ckpt-grpo-control --name grpo-control
    (downloads the latest checkpoint's adapter, merges it onto the M1 merged model, converts to Q8_0 GGUF, writes
     eval/configs/<name>-q8.toml; then serve it and run eval.run_baseline on data/tasks/dev/v1.jsonl as for M1)
uv run python -m eval.grpo_checkpoint_dev judge --control <run dir> --m1 <run dir> --metrics <metrics.jsonl> --out <dir>

The shuffled-reward control PASSES iff (preregistration, owner's reading of it) its dev success is not above M1's 95% Wilson
interval (a control trained on permuted rewards must not improve) AND format validity holds (at most 5% of episodes with an
invalid action: the SFT-to-GRPO bound). It also reports the paired difference and the measured GPU-hours per step.
"""

import argparse
import json
import os
from pathlib import Path

from eval.stats import paired_diff_ci, wilson_ci
from training import config

M1_MERGED = config.DATA_DIR / "models" / "m1-merged" / "ffmpeg-agent-m1-0.6b"
INVALID_MAX_SHARE = 0.05


def judge(control: list[dict], m1: list[dict], metrics: list[dict]) -> dict:
    n = len(control)
    ids = {r["task_id"] for r in control}
    if ids != {r["task_id"] for r in m1}:
        raise ValueError("control and M1 runs cover different dev tasks")
    k, k1 = sum(bool(r["success"]) for r in control), sum(bool(r["success"]) for r in m1)
    p, lo, hi = wilson_ci(k, n)
    p1, lo1, hi1 = wilson_ci(k1, len(m1))
    invalid_episodes = sum(r.get("invalid_turns", 0) > 0 for r in control)
    d, dlo, dhi = paired_diff_ci(
        {r["task_id"]: bool(r["success"]) for r in control},
        {r["task_id"]: bool(r["success"]) for r in m1},
    )
    per_step = [m["gpu_hours"] for m in metrics if "gpu_hours" in m]
    rest = per_step[1:]  # step 1 includes the one-off warm-up
    not_above = p <= hi1
    format_ok = invalid_episodes / n <= INVALID_MAX_SHARE
    return {
        "control": {"k": k, "n": n, "rate": p, "ci95": [lo, hi]},
        "m1": {"k": k1, "n": len(m1), "rate": p1, "ci95": [lo1, hi1]},
        "paired_diff_control_minus_m1": {"diff": d, "ci95": [dlo, dhi]},
        "not_above_m1_ci": not_above,
        "invalid_episodes": invalid_episodes,
        "invalid_share": invalid_episodes / n,
        "format_ok": format_ok,
        "control_passes": bool(not_above and format_ok),
        "gpu_hours_per_step": {
            "steps": len(per_step),
            "mean": sum(per_step) / len(per_step) if per_step else None,
            "mean_without_step1": sum(rest) / len(rest) if rest else None,
            "projected_60_steps": 60 * sum(rest) / len(rest) if rest else None,
        },
    }


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def prepare(repo: str, name: str, step: int | None) -> None:
    from huggingface_hub import snapshot_download

    from training.export.gguf import to_gguf
    from training.export.merge import merge_lora
    from training.grpo.ckpt_sync import HubRemote

    ck = f"checkpoint-{step}" if step else HubRemote(repo).latest()
    if not ck:
        raise SystemExit(f"no checkpoint in {repo}")
    root = config.DATA_DIR / "models"
    hub = root / f"{name}-hub"
    snapshot_download(
        repo,
        local_dir=str(hub),
        allow_patterns=[
            f"checkpoints/{ck}/adapter_*",
            f"checkpoints/{ck}/*.jsonl",
            f"checkpoints/{ck}/trainer_state.json",
        ],
    )
    merged = merge_lora(str(M1_MERGED), hub / "checkpoints" / ck, root / f"{name}-merged" / name)
    tools = config.DATA_DIR / "tools"
    os.environ.setdefault("LLAMA_CPP_DIR", str(tools / "llama.cpp-b12032"))
    quantize = tools / "llama-b12032" / "llama-b12032" / "llama-quantize"
    os.environ.setdefault("LLAMA_QUANTIZE", str(quantize))
    os.environ.setdefault(
        "LLAMA_CONVERT_PYTHON", str(tools / "llama-convert-venv" / "bin" / "python")
    )
    outs = to_gguf(merged, root / f"{name}-gguf", quants=("q8_0",))
    cfg = Path("eval/configs/m1-0.6b-q8.toml").read_text()
    cfg = cfg.replace("ffmpeg-agent-m1-0.6b-q8_0.gguf", outs["q8_0"].name)
    cfg = cfg.replace('model = "ffmpeg-agent-m1-0.6b"', f'model = "{name}"')
    cfg = f"# {name} ({ck} of {repo}), merged onto M1 and served the same way as M1.\n" + cfg
    dest = Path(f"eval/configs/{name}-q8.toml")
    if dest.exists():
        raise SystemExit(f"refusing to overwrite {dest}")
    dest.write_text(cfg)
    info = {
        "checkpoint": ck,
        "gguf": str(outs["q8_0"]),
        "config": str(dest),
        "metrics": str(hub / "checkpoints" / ck / "metrics.jsonl"),
    }
    print(json.dumps(info, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--repo", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--step", type=int)
    j = sub.add_parser("judge")
    j.add_argument("--control", type=Path, required=True, help="run dir of the control on dev")
    j.add_argument("--m1", type=Path, required=True, help="run dir of M1 on dev")
    j.add_argument("--metrics", type=Path, required=True)
    j.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == "prepare":
        prepare(a.repo, a.name, a.step)
        return
    out = judge(_rows(a.control / "results.jsonl"), _rows(a.m1 / "results.jsonl"), _rows(a.metrics))
    a.out.mkdir(parents=True)
    (a.out / "judgement.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
