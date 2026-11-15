"""Markdown results table from one or more baseline dirs (dirs of the same system+model, e.g. a
pilot and the rest, are merged). Refuses to overwrite.

uv run python -m eval.report reports/<date>-phase-0/baselines.md reports/<date>-phase-0/*/
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from eval.stats import paired_diff_ci, wilson_ci
from eval.taxonomy import CATEGORIES, classify


def _load(dirs: list[Path]) -> tuple[dict[str, dict[str, dict]], dict[str, dict[str, dict]]]:
    """Results and transcripts by system label; dirs of the same label (pilot + rest) are merged."""
    systems: dict[str, dict[str, dict]] = defaultdict(dict)
    episodes: dict[str, dict[str, dict]] = defaultdict(dict)
    for d in dirs:
        m = json.loads((d / "manifest.json").read_text())
        label = f"{m['system']}-{m['model']}"
        for line in (d / "results.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r["task_id"] in systems[label]:
                raise ValueError(f"{label}: task {r['task_id']} appears in two result dirs")
            systems[label][r["task_id"]] = r
        eps_path = d / "episodes.jsonl"
        if eps_path.exists():
            for line in eps_path.read_text().splitlines():
                e = json.loads(line)
                episodes[label][e["task_id"]] = e
    return systems, episodes


def _pct(ci: tuple[float, float, float]) -> str:
    return f"{ci[0]:.0%} [{ci[1]:.0%}, {ci[2]:.0%}]"


def write_report(out: Path, dirs: list[Path]) -> None:
    if out.exists():
        raise FileExistsError(out)
    systems, episodes = _load(dirs)
    lines = [
        "# Baseline results",
        "",
        "Success with Wilson 95% CI (D-021); paired differences use a paired bootstrap. Failed, invalid and errored "
        "episodes count as failures.",
        "",
        "| System | n | success | graded | ambiguous | unsupported | runs/task | invalid turns/task |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for label, rows in sorted(systems.items()):
        rs = list(rows.values())
        graded = [r["success"] for r in rs if not any(r["flags"].values())]
        amb = [r["success"] for r in rs if r["flags"]["ambiguous"]]
        uns = [r["success"] for r in rs if r["flags"]["unsupported"]]
        frac = lambda xs: f"{sum(xs)}/{len(xs)}"  # noqa: E731
        lines.append(
            f"| {label} | {len(rs)} | {_pct(wilson_ci(sum(r['success'] for r in rs), len(rs)))} | {frac(graded)} | "
            f"{frac(amb)} | {frac(uns)} | {sum(r['runs'] for r in rs) / len(rs):.2f} | "
            f"{sum(r['invalid_turns'] for r in rs) / len(rs):.2f} |"
        )
    families = sorted(
        {f for rows in systems.values() for r in rows.values() for f in r["families"]},
        key=lambda f: int(f[1:]),
    )
    lines += [
        "",
        "## By family (tasks containing the family)",
        "",
        "| System | " + " | ".join(families) + " |",
        "|---|" + "---|" * len(families),
    ]
    for label, rows in sorted(systems.items()):
        cells = []
        for f in families:
            xs = [r["success"] for r in rows.values() if f in r["families"]]
            cells.append(f"{sum(xs)}/{len(xs)}" if xs else "–")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    graded = {
        label: [r for r in rows.values() if not any(r["flags"].values())]
        for label, rows in systems.items()
    }
    lines += [
        "",
        "## Graded tasks by number of chore families (single-step = 1 family, multi-step = 2+)",
        "",
        "| System | single-step | multi-step |",
        "|---|---|---|",
    ]
    for label, rows in sorted(graded.items()):
        single = [r["success"] for r in rows if len(r["families"]) == 1]
        multi = [r["success"] for r in rows if len(r["families"]) >= 2]
        lines.append(f"| {label} | {sum(single)}/{len(single)} | {sum(multi)}/{len(multi)} |")
    lines += [
        "",
        "## Failure taxonomy (count of FAILED episodes per category; see eval/taxonomy.py)",
        "",
        "| System | failed | " + " | ".join(CATEGORIES) + " |",
        "|---|---|" + "---|" * len(CATEGORIES),
    ]
    for label, rows in sorted(systems.items()):
        counts = {c: 0 for c in CATEGORIES}
        for tid, r in rows.items():
            cat = classify(r, episodes[label].get(tid))
            if cat:
                counts[cat] += 1
        lines.append(
            f"| {label} | {sum(counts.values())} | "
            + " | ".join(str(counts[c] or "") for c in CATEGORIES)
            + " |"
        )
    diffs = [
        (x, b) for x in systems if x.startswith("X1") for b in systems if b.startswith(("B0", "B2"))
    ]
    if diffs:
        lines += ["", "## Paired differences (percentage points, paired bootstrap 95% CI)", ""]
        for x, b in diffs:
            a_s = {k: r["success"] for k, r in systems[x].items()}
            b_s = {k: r["success"] for k, r in systems[b].items()}
            try:
                m, lo, hi = paired_diff_ci(a_s, b_s)
                lines.append(f"- {x} − {b}: {m * 100:+.1f} [{lo * 100:+.1f}, {hi * 100:+.1f}]")
            except ValueError as e:
                lines.append(f"- {x} − {b}: not comparable ({e})")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    write_report(Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]])
