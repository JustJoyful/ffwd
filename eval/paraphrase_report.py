"""Originals vs paraphrases on the SAME kept tasks, per system, Wilson CIs + paired difference.

uv run python -m eval.paraphrase_report --para-dir reports/<d> --out reports/<d>/paraphrase-robustness.md
"""

import argparse
import json
from pathlib import Path

from eval.stats import paired_diff_ci, wilson_ci

FU = Path("reports/2026-11-16-phase0-followups")
P0 = Path("reports/2026-11-15-phase-0")


def load(*dirs: Path) -> dict[str, bool]:
    """Later dirs override earlier ones (the checker-v1 regrade replaces the 3 F11 rows)."""
    out: dict[str, bool] = {}
    for d in dirs:
        for line in (d / "results.jsonl").read_text().splitlines():
            r = json.loads(line)
            out[r["task_id"]] = bool(r["success"])
    return out


def fmt(k: int, n: int) -> str:
    p, lo, hi = wilson_ci(k, n)
    return f"{k}/{n} = {p:.0%} [{lo:.0%}, {hi:.0%}]"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--para-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    log = [json.loads(x) for x in (a.para_dir / "paraphrase-log.jsonl").read_text().splitlines()]
    kept = [r["task_id"] for r in log if not r["dropped"]]
    systems = {
        "B0 regex/preset": (
            load(FU / "B0-regex"),
            load(a.para_dir / "B0-regex-para"),
        ),
        "X1 DeepSeek V4 Flash": (
            load(
                P0 / "X1-deepseek-flash-pilot",
                P0 / "X1-deepseek-flash-pilot-rest",
                P0 / "X1-deepseek-flash-rest",
                FU / "X1-regraded-f11-checker-v1",
            ),
            load(a.para_dir / "X1-deepseek-para"),
        ),
    }
    lines = [
        "# Paraphrase robustness (dev only)",
        "",
        f"{len(kept)} of {len(log)} tasks kept; same tasks on both sides. Wilson 95% CIs; "
        "difference = paraphrase − original, paired bootstrap 95% CI.",
        "",
        "| System | Original | Paraphrase | Diff (pp) |",
        "|---|---|---|---|",
    ]
    for name, (orig, para) in systems.items():
        o = [orig[t] for t in kept]
        p = [para[t] for t in kept]
        d, lo, hi = paired_diff_ci({t: para[t] for t in kept}, {t: orig[t] for t in kept})
        lines.append(
            f"| {name} | {fmt(sum(o), len(o))} | {fmt(sum(p), len(p))} | "
            f"{d * 100:+.1f} [{lo * 100:+.1f}, {hi * 100:+.1f}] |"
        )
    lines += ["", "## Tasks whose outcome changed", ""]
    for name, (orig, para) in systems.items():
        flips = [(t, orig[t], para[t]) for t in kept if orig[t] != para[t]]
        lines.append(f"**{name}**: " + (", ".join(f"`{t}` {o}→{p}" for t, o, p in flips) or "none"))
        lines.append("")
    lines += ["## Dropped paraphrases", ""]
    lines += [
        f"- `{r['task_id']}`: {r['dropped']} — “{r['paraphrase']}”" for r in log if r["dropped"]
    ]
    a.out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
