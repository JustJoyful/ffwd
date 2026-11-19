"""How well does a system recover from a failing first command? Dev only (owner instruction 20 Nov 2026).

uv run python -m eval.recovery_eval --run reports/<dir>/M1-0.6b-q8 --recovery data/tasks-hard/dev-recovery \
    --model-config eval/configs/m1-0.6b-q8.toml --out reports/<date>-<name>

Two measurements, both on DEV tasks:
* natural: in an existing run, the tasks whose FIRST run failed the check, and how many of them still ended passing;
* perturbed start: each dev task re-run from a scripted opening (gold spec + a perturbed run the checker verifiably
  fails, training.taskgen.recovery), so every task needs the model to read the failure and fix it. Needs a running
  llama-server (the config's `server_args`).
Wilson 95% intervals; failed, invalid and errored episodes count as failures.
"""

import argparse
import hashlib
import json
import tomllib
from pathlib import Path

from eval.run_baseline import load_corpus, run_baseline
from eval.stats import wilson_ci
from training.env.constrained import load_prompt
from training.policies import policy_from_config
from training.taskgen.recovery import OpeningPolicy, openings_for


def first_run_failed(episode: dict) -> bool | None:
    """True/False if the episode ran something and its first run did/did not fail the check; None if it never ran."""
    for turn in episode["turns"]:
        try:
            a = json.loads(turn["assistant"])
        except ValueError:
            continue
        if a.get("action") == "run":
            obs = turn["observation"]
            if "run_ok" not in obs:  # rejected by the validator before running
                return True
            checks = obs.get("checks") or {}
            return not (obs["run_ok"] and checks and all(c.get("passed") for c in checks.values()))
    return None


def natural_recovery(run_dir: Path) -> dict:
    """Of the tasks whose first run failed, the share that ended passing (an existing run's own recoveries)."""
    res = [json.loads(x) for x in (run_dir / "results.jsonl").read_text().splitlines()]
    eps = [json.loads(x) for x in (run_dir / "episodes.jsonl").read_text().splitlines()]
    failed = [r for r, e in zip(res, eps, strict=True) if first_run_failed(e)]
    k = sum(bool(r["success"]) for r in failed)
    out = {"tasks_with_a_failed_first_run": len(failed), "recovered": k, "of_tasks": len(res)}
    if failed:
        p, lo, hi = wilson_ci(k, len(failed))
        out |= {"rate": p, "ci95": [lo, hi]}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run", type=Path, required=True, help="an existing dev run dir (natural recovery)"
    )
    ap.add_argument(
        "--recovery", type=Path, required=True, help="dir with tasks.jsonl + recovery.jsonl (dev)"
    )
    ap.add_argument("--model-config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    raw = (a.recovery / "tasks.jsonl").read_bytes()
    tasks = [json.loads(x) for x in raw.decode().splitlines()]
    if any(t["split"] != "dev" for t in tasks):
        raise SystemExit("recovery_eval reads dev tasks only")
    rows = [json.loads(x) for x in (a.recovery / "recovery.jsonl").read_text().splitlines()]
    cfg = tomllib.loads(a.model_config.read_text())
    policy = OpeningPolicy(policy_from_config(a.model_config, None), openings_for(tasks, rows))
    a.out.mkdir(parents=True)
    run_dir = run_baseline(
        system="M1",
        policy=policy,
        tasks=tasks,
        out=a.out / "perturbed-start",
        corpus=load_corpus(),
        meta={
            "model": cfg["model"], "quant": cfg.get("quant"), "temperature": cfg.get("temperature", 0.0),
            "model_config": str(a.model_config), "system_prompt": cfg["system_prompt"],
            "constrained_decoding": False, "require_spec": True, "stop_after_ask": True,
            "scripted_opening": "gold spec + perturbed run (training.taskgen.recovery)",
        },
        tasks_sha256=hashlib.sha256(raw).hexdigest(),
        system_prompt_text=load_prompt(cfg["system_prompt"]),
        require_spec=True,
        stop_after_ask=True,
    )  # fmt: skip
    res = {
        r["task_id"]: r
        for r in map(json.loads, (run_dir / "results.jsonl").read_text().splitlines())
    }
    k = sum(bool(r["success"]) for r in res.values())
    p, lo, hi = wilson_ci(k, len(res))
    by_op: dict[str, list[int]] = {}
    for r in rows:
        d = by_op.setdefault(r["operator"], [0, 0])
        d[0] += bool(res[r["task_id"]]["success"])
        d[1] += 1
    out = {
        "natural": natural_recovery(a.run),
        "perturbed_start": {
            "n": len(res), "recovered": k, "rate": p, "ci95": [lo, hi],
            "by_operator": {op: f"{v[0]}/{v[1]}" for op, v in sorted(by_op.items())},
            "mean_runs": sum(r["runs"] for r in res.values()) / len(res),
        },
    }  # fmt: skip
    (a.out / "recovery.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
