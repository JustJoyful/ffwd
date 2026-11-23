"""Descriptive extras for the Phase 1 report: failure taxonomy and GRPO telemetry summary.

Additive only: reads results the driver already wrote and writes two markdown files next to `summary.md`.
It computes no preregistered quantity and touches no checker, metric or selection.

    uv run python -m eval.phase1_extras --runs-root reports/2026-11-22-phase1-runs \
        --telemetry <checkpoint-dir>/telemetry.jsonl --out reports/<date>-phase-1
"""

import argparse
import json
from collections import Counter
from pathlib import Path

GENERATED_SPLITS = ("test-iid", "test-phrasing", "test-compositional")


def task_kind(result: dict) -> str:
    """supported | ambiguous (the right move is ask_user) | unsupported (the right move is refuse)."""
    flags = result.get("flags") or {}
    if flags.get("unsupported"):
        return "unsupported"
    return "ambiguous" if flags.get("ambiguous") else "supported"


def taxonomy(runs_root: Path, systems: list[str]) -> dict[str, dict[tuple[str, str], list[int]]]:
    """{system: {(task_kind, end_reason): [failures, tasks_of_that_kind]}} pooled over the generated splits.

    A failure is any episode with success false, so timeouts, malformed output and errors count (RULES 2).
    """
    out: dict[str, dict[tuple[str, str], list[int]]] = {}
    for s in systems:
        kinds: Counter = Counter()
        fails: Counter = Counter()
        for sp in GENERATED_SPLITS:
            for line in (
                (runs_root / "runs" / f"{s}-{sp}" / "results.jsonl").read_text().splitlines()
            ):
                r = json.loads(line)
                kinds[task_kind(r)] += 1
                if not r["success"]:
                    fails[(task_kind(r), r["end_reason"])] += 1
        out[s] = {k: [n, kinds[k[0]]] for k, n in sorted(fails.items())}
    return out


def taxonomy_md(tax: dict) -> str:
    lines = [
        "# Failure taxonomy (descriptive, pooled over test-iid + test-phrasing + test-compositional)",
        "",
        "Rows are failed episodes by the kind of task and how the episode ended. `run_budget` = used all runs without a passing check; "
        "`turn_budget` = ran out of turns (includes repeated invalid actions); `asked` / `unsupported` = the system stopped to ask or refuse "
        "when that was the wrong move for the task kind. Tasks where the right move was to ask or refuse are scored by the same success rule as the rest.",
        "",
        "| System | task kind | ended | failed | of tasks of that kind |",
        "|---|---|---|---|---|",
    ]
    for s, rows in tax.items():
        for (kind, reason), (n, total) in rows.items():
            lines.append(f"| {s} | {kind} | {reason} | {n} | {total} |")
    return "\n".join(lines) + "\n"


def telemetry_summary(path: Path, window: int = 10) -> dict:
    steps = [json.loads(line) for line in path.read_text().splitlines()]
    keys = [
        "pass_rate",
        "mean_reward",
        "invalid_action_rate",
        "no_signal_group_share",
        "runs_per_rollout",
        "ask_rate_on_supported",
        "refusal_rate_on_supported",
    ]

    def mean(chunk: list[dict], k: str) -> float:
        return sum(x[k] for x in chunk) / len(chunk)

    return {
        "steps": len(steps),
        "rollouts_per_step": steps[0]["n_rollouts"],
        "window": window,
        **{k: {"first": mean(steps[:window], k), "last": mean(steps[-window:], k)} for k in keys},
    }


def telemetry_md(t: dict) -> str:
    lines = [
        "# GRPO telemetry summary (M3, training run; descriptive)",
        "",
        f"{t['steps']} steps, {t['rollouts_per_step']} rollouts per step. Mean over the first and last {t['window']} steps "
        "(training-set tasks, sampled rollouts: not test performance).",
        "",
        "| metric | first steps | last steps |",
        "|---|---|---|",
    ]
    for k, v in t.items():
        if isinstance(v, dict):
            lines.append(f"| {k} | {v['first']:.3f} | {v['last']:.3f} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", type=Path, required=True)
    ap.add_argument("--telemetry", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True, help="an existing report directory")
    ap.add_argument("--systems", nargs="+", default=["B0", "B2", "M1", "M3", "X1"])
    a = ap.parse_args()
    for name in ("failure_taxonomy.md", "telemetry.md"):
        if (a.out / name).exists():
            raise FileExistsError(a.out / name)  # reports are never overwritten
    (a.out / "failure_taxonomy.md").write_text(taxonomy_md(taxonomy(a.runs_root, a.systems)))
    (a.out / "telemetry.md").write_text(telemetry_md(telemetry_summary(a.telemetry)))
    print(f"wrote failure_taxonomy.md and telemetry.md in {a.out}")


if __name__ == "__main__":
    main()
