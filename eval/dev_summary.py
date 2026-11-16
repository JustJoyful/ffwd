"""Wilson-CI table of systems on one dev run set, overall and by difficulty (dev only; never use for test splits).

uv run python -m eval.dev_summary --out reports/<dir>/summary.md --title "..." B0=<run dir> B2=<run dir>
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from eval.stats import wilson_ci


def _fmt(k: int, n: int) -> str:
    p, lo, hi = wilson_ci(k, n)
    return f"{k}/{n} = {p:.0%} [{lo:.0%}, {hi:.0%}]"


def summarize(runs: dict[str, Path], title: str) -> str:
    data = {
        s: [json.loads(x) for x in (d / "results.jsonl").read_text().splitlines()]
        for s, d in runs.items()
    }
    diffs = sorted({r["difficulty"] for rows in data.values() for r in rows})
    lines = [f"# {title}", "", "Dev only. Wilson 95% intervals; failed/invalid/errored episodes count as failures.", "",
             "| System | overall | " + " | ".join(f"{d} famil{'y' if d == 1 else 'ies'}" for d in diffs) + " | ambiguous | unsupported |",
             "|---|---|" + "---|" * (len(diffs) + 2)]  # fmt: skip
    for s, rows in data.items():
        by = defaultdict(lambda: [0, 0])
        for r in rows:
            by[r["difficulty"]][0] += r["success"]
            by[r["difficulty"]][1] += 1
        amb = [r for r in rows if r["flags"]["ambiguous"]]
        uns = [r for r in rows if r["flags"]["unsupported"]]
        cells = [_fmt(*by[d]) if by[d][1] else "-" for d in diffs]
        lines.append(
            f"| {s} | {_fmt(sum(r['success'] for r in rows), len(rows))} | " + " | ".join(cells)
            + f" | {_fmt(sum(r['success'] for r in amb), len(amb)) if amb else '-'} | {_fmt(sum(r['success'] for r in uns), len(uns)) if uns else '-'} |"
        )  # fmt: skip
    ends = {s: defaultdict(int) for s in data}
    for s, rows in data.items():
        for r in rows:
            ends[s][r["end_reason"]] += 1
    lines += [
        "",
        "End reasons: " + "; ".join(f"{s}: {dict(sorted(e.items()))}" for s, e in ends.items()),
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", default="Dev baselines")
    ap.add_argument("runs", nargs="+", help="LABEL=run_dir")
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    text = summarize({k: Path(v) for k, v in (x.split("=", 1) for x in a.runs)}, a.title)
    a.out.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
