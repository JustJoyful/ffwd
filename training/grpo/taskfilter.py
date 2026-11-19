"""Pre-GRPO task filter (T6): keep tasks the model solves sometimes, not always or never.

GRPO learns from reward differences inside a group of rollouts for the same prompt. A task the model
always solves (rate 1) or never solves (rate 0) gives every rollout the same reward, so it carries
no gradient signal and just burns FFmpeg time. We sample the (SFT) model K times per TRAIN task,
keep tasks whose pass rate is inside a band (default 20-80%, training/config.py), and store the
table with the run so the selection is reproducible and auditable.

Never run on dev/test tasks: the table would leak their difficulty into training choices (RULES §4.5).

  uv run python -m training.grpo.taskfilter --tasks train.jsonl --policy-config eval/configs/<sft>.toml \
      --k 8 --out reports/<date>-<run>/taskfilter
"""

import argparse
import hashlib
import json
import random
import shutil
import sys
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from training import config
from training.env.loop import Policy, run_episode, score

Sampler = Callable[[dict, int], list[bool]]  # (task, k) -> k pass/fail results


def episode_sampler(
    policy_factory: Callable[[], Policy],
    corpus: dict[str, Path],
    jobs_root: Path,
    max_runs: int = config.MAX_RUNS_PER_JOB,
    system_prompt_text: str | None = None,
    require_spec: bool = False,
    stop_after_ask: bool = False,
) -> Sampler:
    """Sample by running real episodes (probe -> run -> check) with a fresh policy for each one."""

    def one(task: dict) -> bool:
        job = jobs_root / uuid.uuid4().hex
        try:
            return score(
                task,
                run_episode(
                    task,
                    policy_factory(),
                    corpus=corpus,
                    job_dir=job,
                    max_runs=max_runs,
                    system_prompt_text=system_prompt_text,
                    require_spec=require_spec,
                    stop_after_ask=stop_after_ask,
                ),
            )
        finally:  # thousands of episodes: only the pass/fail is kept, so outputs must not pile up on disk
            shutil.rmtree(job, ignore_errors=True)

    def sample(task: dict, k: int) -> list[bool]:
        return [one(task) for _ in range(k)]

    return sample


def pass_rate_table(
    tasks: list[dict],
    sample: Sampler,
    k: int,
    band: tuple[float, float],
    meta: dict,
    *,
    workers: int = 1,
    done: dict[str, int] | None = None,
    on_row: Callable[[str, int], None] | None = None,
) -> dict:
    """`workers` tasks are sampled at once (the sampler must be thread-safe). `done` (task id -> passes) are reused
    instead of re-sampled; `on_row(task_id, passes)` is called as each task finishes (the CLI appends to rows.jsonl so
    a killed multi-hour run resumes). The table is identical for any `workers`."""
    lo, hi = band
    if not 0.0 <= lo <= hi <= 1.0:
        raise ValueError(f"band must satisfy 0 <= lo <= hi <= 1, got {band}")
    for t in tasks:
        if t["split"] not in config.PASS_RATE_ALLOWED_SPLITS:
            raise ValueError(
                f"task {t['id']} has split {t['split']!r}; only {config.PASS_RATE_ALLOWED_SPLITS} may be filtered"
            )
    done = done or {}

    def passes_of(t: dict) -> int:
        if t["id"] in done:
            return done[t["id"]]
        n = sum(sample(t, k))
        if on_row:
            on_row(t["id"], n)
        return n

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        all_passes = list(pool.map(passes_of, tasks))
    rows: dict[str, dict] = {}
    for t, passes in zip(tasks, all_passes, strict=True):
        rate = passes / k
        reason = "too_hard" if rate < lo else "too_easy" if rate > hi else "in_band"
        rows[t["id"]] = {
            "passes": passes,
            "k": k,
            "rate": rate,
            "keep": reason == "in_band",
            "reason": reason,
        }
    summary = {
        "total": len(rows),
        "kept": sum(r["keep"] for r in rows.values()),
        "too_easy": sum(r["reason"] == "too_easy" for r in rows.values()),
        "too_hard": sum(r["reason"] == "too_hard" for r in rows.values()),
    }
    return {
        "meta": {**meta, "k": k, "band": [lo, hi], "date": datetime.now(UTC).isoformat()},
        "summary": summary,
        "tasks": rows,
    }


def select_tasks(tasks: list[dict], table: dict) -> list[dict]:
    kept = [t for t in tasks if table["tasks"][t["id"]]["keep"]]
    if not kept:
        raise ValueError(
            "no tasks inside the pass-rate band: widen the band or check the model/sampler before training"
        )
    return kept


def apply_filter(tasks: list[dict], table_path: Path, run_dir: Path) -> list[dict]:
    """In-band tasks from a saved table; the table is copied into the run dir so it is stored (and
    synced with checkpoints) alongside the run it shaped."""
    table = load_table(table_path)
    kept = select_tasks(tasks, table)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "pass_rates.json").write_text(table_path.read_text())
    return kept


def save_table(table: dict, path: Path) -> Path:
    if path.exists():
        raise FileExistsError(path)  # reports are never overwritten (RULES §4.7)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(table, indent=2) + "\n")
    return path


def load_table(path: Path) -> dict:
    return json.loads(path.read_text())


def main(argv: list[str] | None = None) -> None:
    from training.corpus.make_synthetic import ensure_corpus
    from training.policies import policy_from_config
    from training.teacher.generate import load_prompt_v1

    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, required=True)
    ap.add_argument("--policy-config", type=Path, required=True)
    ap.add_argument("--k", type=int, default=config.PASS_RATE_SAMPLES)
    ap.add_argument(
        "--band", type=float, nargs=2, default=config.PASS_RATE_BAND, metavar=("LO", "HI")
    )
    ap.add_argument(
        "--temperature",
        type=float,
        default=1.0,
        help="must be > 0: K identical samples would measure nothing",
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--workers", type=int, default=1, help="tasks sampled in parallel (match llama-server -np)"
    )
    ap.add_argument(
        "--sample",
        type=int,
        help="use a seeded random sample of this many tasks (a subset table: say so wherever it is quoted)",
    )
    ap.add_argument("--seed", type=int, default=config.BOOTSTRAP_SEED)
    ap.add_argument(
        "--phase1",
        action="store_true",
        help="prompt v1, spec-first, stop after a clarification (the Phase 1 protocol)",
    )
    ap.add_argument("--allow-draft-prompt", action="store_true")
    a = ap.parse_args(argv)
    if a.temperature <= 0:
        sys.exit("--temperature must be > 0")
    raw = a.tasks.read_bytes()
    tasks = [json.loads(x) for x in raw.decode().splitlines() if x.strip()]
    if a.sample:
        tasks = random.Random(a.seed).sample(sorted(tasks, key=lambda t: t["id"]), a.sample)
    corpus = ensure_corpus(config.CORPUS_DIR, ids={c for t in tasks for c in t["inputs"]})
    policy = policy_from_config(a.policy_config, None)
    policy.temperature = a.temperature
    sampler = episode_sampler(
        lambda: policy,
        corpus,
        config.JOBS_DIR / "taskfilter",
        system_prompt_text=load_prompt_v1(a.allow_draft_prompt) if a.phase1 else None,
        require_spec=a.phase1,
        stop_after_ask=a.phase1,
    )
    rows_file, lock = (
        a.out / "rows.jsonl",
        threading.Lock(),
    )  # resumable: one line per finished task
    a.out.mkdir(parents=True, exist_ok=True)
    done = (
        {r["id"]: r["passes"] for r in map(json.loads, rows_file.read_text().splitlines())}
        if rows_file.exists()
        else {}
    )

    def on_row(tid: str, passes: int) -> None:
        with lock, rows_file.open("a") as f:
            f.write(json.dumps({"id": tid, "passes": passes}) + "\n")

    table = pass_rate_table(
        tasks,
        sampler,
        a.k,
        tuple(a.band),
        {
            "policy_config": str(a.policy_config),
            "model": policy.model,
            "temperature": a.temperature,
            "seed": a.seed,
            "tasks_sha256": hashlib.sha256(raw).hexdigest(),
            "sample": a.sample,
            "n_tasks": len(tasks),
            "workers": a.workers,
        },
        workers=a.workers,
        done=done,
        on_row=on_row,
    )
    save_table(table, a.out / "pass_rates.json")
    kept = select_tasks(tasks, table)  # fails loudly if the band is empty
    (a.out / "tasks-selected.jsonl").write_text("".join(json.dumps(t) + "\n" for t in kept))
    print(json.dumps(table["summary"]))


if __name__ == "__main__":
    main()
