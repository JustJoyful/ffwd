"""Summarise a GRPO pass-rate table (training/grpo/taskfilter.py, plan T18): how much of the TRAIN set is in the 20-80% band?

uv run python -m eval.passrate_report --table <dir>/pass_rates.json --tasks data/tasks/train/v1.jsonl \
    --sft-sources data/teacher/bulk-20261119 --out <dir>/summary.md

GRPO learns only from tasks whose K samples disagree. Share in band overall and by group, with Wilson 95% intervals.
`--sft-sources` marks tasks the M1 model was fine-tuned on (teacher kept, paraphrase and oracle trajectories): their pass
rates are inflated by having been trained on, so they are reported separately. Train tasks only; never dev/test.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from eval.stats import wilson_ci


def group_keys(task: dict) -> list[str]:
    f = task["flags"]
    kind = "ambiguous" if f["ambiguous"] else "unsupported" if f["unsupported"] else None
    keys = [
        f"kind: {kind}" if kind else f"families: {len(task['families'])}",
        f"difficulty: {task['difficulty']}",
    ]
    return keys + [f"involves {fam}" for fam in task["families"]]


def analyse(table: dict, tasks: list[dict], sft_ids: set[str] | None = None) -> dict:
    by_id = {t["id"]: t for t in tasks}
    groups: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "in_band": 0, "too_easy": 0, "too_hard": 0}
    )

    def add(key: str, reason: str) -> None:
        groups[key]["n"] += 1
        groups[key][reason] += 1

    for tid, row in table["tasks"].items():
        add("ALL", row["reason"])
        for k in group_keys(by_id[tid]):
            add(k, row["reason"])
        if sft_ids is not None:
            add("in M1's SFT data" if tid in sft_ids else "NOT in M1's SFT data", row["reason"])
    for g in groups.values():
        g["share_in_band"], g["ci_lo"], g["ci_hi"] = wilson_ci(g["in_band"], g["n"])
    return dict(sorted(groups.items(), key=lambda kv: (kv[0] != "ALL", kv[0])))


def render(groups: dict, meta: dict) -> str:
    sample = f" (seeded sample of {meta['sample']})" if meta.get("sample") else ""
    lines = [
        f"Pass-rate table: K={meta['k']}, band {meta['band']}, temperature {meta['temperature']}, "
        f"model `{meta['model']}`, {meta.get('n_tasks', '?')} tasks{sample}",
        "",
        "| group | n | in band | too easy (>80%) | too hard (<20%) | share in band [95% CI] |",
        "|---|---|---|---|---|---|",
    ]
    for k, g in groups.items():
        lines.append(
            f"| {k} | {g['n']} | {g['in_band']} | {g['too_easy']} | {g['too_hard']} | "
            f"{g['share_in_band']:.0%} [{g['ci_lo']:.0%}, {g['ci_hi']:.0%}] |"
        )
    return "\n".join(lines) + "\n"


def sft_task_ids(sources: Path) -> set[str]:
    """Train task ids in the trajectories M1 was trained on (`+pK` suffix = paraphrase of that task)."""
    ids: set[str] = set()
    for name in ("kept.jsonl", "paraphrases.jsonl", "oracle/kept.jsonl"):
        lines = (sources / name).read_text().splitlines()
        ids |= {json.loads(x)["task_id"].split("+")[0] for x in lines}
    return ids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", type=Path, required=True)
    ap.add_argument("--tasks", type=Path, required=True)
    ap.add_argument("--sft-sources", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    table = json.loads(a.table.read_text())
    tasks = [json.loads(x) for x in a.tasks.read_text().splitlines()]
    if any(t["split"] not in ("train", "toy") for t in tasks):
        raise SystemExit("pass-rate reports read train tasks only")
    groups = analyse(table, tasks, sft_task_ids(a.sft_sources) if a.sft_sources else None)
    a.out.write_text(render(groups, table["meta"]))
    (a.out.parent / "groups.json").write_text(json.dumps(groups, indent=1) + "\n")
    print(render(groups, table["meta"]))


if __name__ == "__main__":
    main()
