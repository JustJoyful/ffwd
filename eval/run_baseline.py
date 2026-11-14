"""Run one system over a task file (EVALUATION §3). Writes results.jsonl, episodes.jsonl and
manifest.json into a FRESH directory (RULES §4.7). Every task gets a line; errors count as failures.

uv run python -m eval.run_baseline --system B2 --model-config eval/configs/qwen3-0.6b.toml \
    --tasks data/tasks/dev/spike-v0.jsonl --out reports/<date>-phase-0/B2-qwen3-0.6b
"""

import argparse
import dataclasses
import hashlib
import json
import os
import platform
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from training import config
from training.env.loop import Policy, run_episode, score
from training.policies import policy_from_config
from training.teacher.budget import BudgetExceeded, BudgetGuard

SYSTEMS = {
    "B1": 1,
    "B2": config.MAX_RUNS_PER_JOB,
    "X1": config.MAX_RUNS_PER_JOB,
}  # system -> max runs


def _cmd(argv: list[str]) -> str:
    try:
        return subprocess.run(
            argv, shell=False, capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _hardware() -> dict:
    mem = (
        next(
            (
                line.split()[1]
                for line in Path("/proc/meminfo").read_text().splitlines()
                if line.startswith("MemTotal")
            ),
            None,
        )
        if Path("/proc/meminfo").exists()
        else None
    )
    return {
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "ram_gb": round(int(mem) / 2**20, 1) if mem else None,
        "gpu": _cmd(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]) or None,
    }


def load_corpus(manifest: Path = config.CORPUS_DIR / "manifest.json") -> dict[str, Path]:
    """Corpus clips by id, verifying each file against its pinned hash."""
    corpus = {}
    for rec in json.loads(manifest.read_text()):
        path = manifest.parent / rec["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != rec["sha256"]:
            raise ValueError(f"corpus clip {rec['id']} does not match its manifest hash")
        corpus[rec["id"]] = path
    return corpus


def run_baseline(
    *,
    system: str,
    policy: Policy,
    tasks: list[dict],
    out: Path,
    corpus: dict[str, Path],
    meta: dict,
    guard: BudgetGuard | None = None,
    tasks_sha256: str | None = None,
    jobs_root: Path = config.JOBS_DIR,
) -> Path:
    out.mkdir(parents=True, exist_ok=False)  # refuses to overwrite a report
    started = datetime.now(UTC).isoformat()
    stopped_reason = None
    with (out / "results.jsonl").open("w") as res, (out / "episodes.jsonl").open("w") as eps:
        for task in tasks:
            row = {
                "task_id": task["id"],
                "families": task["families"],
                "difficulty": task["difficulty"],
                "flags": task["flags"],
            }
            spent_before = guard.spent(run_only=True) if guard else 0.0
            try:
                ep = run_episode(
                    task,
                    policy,
                    corpus=corpus,
                    job_dir=jobs_root / out.name / task["id"],
                    max_runs=SYSTEMS[system],
                )
                row |= {
                    "success": score(task, ep),
                    "runs": ep.runs,
                    "invalid_turns": ep.invalid_turns,
                    "end_reason": ep.end_reason,
                }
                eps.write(json.dumps(dataclasses.asdict(ep)) + "\n")
            except BudgetExceeded as e:
                row |= {
                    "success": False,
                    "runs": 0,
                    "invalid_turns": 0,
                    "end_reason": "error",
                    "error": str(e),
                }
                stopped_reason = f"budget: {e}"
            except Exception as e:  # recorded, never dropped (RULES §4.2)
                row |= {
                    "success": False,
                    "runs": 0,
                    "invalid_turns": 0,
                    "end_reason": "error",
                    "error": f"{type(e).__name__}: {e}"[:300],
                }
            row["cost_usd"] = (guard.spent(run_only=True) - spent_before) if guard else 0.0
            res.write(json.dumps(row) + "\n")
            res.flush()
            if stopped_reason:
                break
    manifest = {
        "git_commit": _cmd(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(_cmd(["git", "status", "--porcelain"])),
        "protocol_version": config.PROTOCOL_VERSION,
        "ffmpeg_version": (
            _cmd([config.FFMPEG_BIN, "-version"]).splitlines()[0]
            if _cmd([config.FFMPEG_BIN, "-version"])
            else None
        ),
        "system": system,
        **meta,
        "tasks_sha256": tasks_sha256 or "",
        "n_tasks": len(tasks),
        "hardware": _hardware(),
        "started": started,
        "finished": datetime.now(UTC).isoformat(),
        "stopped_reason": stopped_reason,
        "cost_usd": guard.spent(run_only=True) if guard else 0.0,
        "cache_hit_ratio": guard.cache_hit_ratio() if guard else None,
    }
    if not manifest["tasks_sha256"]:
        manifest["tasks_sha256"] = hashlib.sha256(
            json.dumps(tasks, sort_keys=True).encode()
        ).hexdigest()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return out


def _preregistered() -> bool:
    prereg = config.REPO_ROOT / "eval" / "PREREGISTRATION.md"
    return prereg.exists() and "Status: FINAL" in prereg.read_text()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", choices=sorted(SYSTEMS), required=True)
    ap.add_argument("--model-config", type=Path, required=True)
    ap.add_argument("--tasks", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--budget-usd", type=float, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.out.exists():
        sys.exit(f"refusing to overwrite {a.out}")
    if not _preregistered():
        sys.exit("eval/PREREGISTRATION.md must say 'Status: FINAL' before any baseline run")
    raw = a.tasks.read_bytes()
    tasks = [json.loads(x) for x in raw.decode().splitlines()][a.offset :][: a.limit]
    cfg = tomllib.loads(a.model_config.read_text())
    guard = None
    if cfg.get("paid"):
        if a.budget_usd is None:
            sys.exit("paid systems need --budget-usd (pilot cap)")
        guard = BudgetGuard(
            config.LEDGER_PATH,
            config.BUDGET_LIFETIME_USD,
            a.budget_usd,
            a.out.name,
            dry_run=a.dry_run,
        )
    policy = policy_from_config(a.model_config, guard)
    meta = {
        "model": config.DEEPSEEK_MODEL_ID if cfg.get("paid") else cfg["model"],
        "quant": cfg.get("quant"),
        "temperature": cfg.get("temperature", 0.0),
        "model_config": str(a.model_config),
        "offset": a.offset,
        "limit": a.limit,
        "dry_run": a.dry_run,
    }
    out = run_baseline(
        system=a.system,
        policy=policy,
        tasks=tasks,
        out=a.out,
        corpus=load_corpus(),
        meta=meta,
        guard=guard,
        tasks_sha256=hashlib.sha256(raw).hexdigest(),
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
