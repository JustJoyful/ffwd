"""G3 criterion (a), computed (owner instruction 20 Nov 2026): no judgment calls.

uv run python -m eval.g3_criteria --tables <widened pass_rates.json> <recovery pass_rates.json> --out <file.json>

(a) = pooled in-band (20-80%) share of the widened + recovery pilots >= config.G3_MIN_IN_BAND_SHARE AND the implied
in-band task count at full scale >= config.G3_MIN_IN_BAND_TASKS. "Full scale" is `config.HARD_FULL_SCALE_N` candidates
(the lower end of the 3,000-4,000 sizing proposed in reports/2026-11-20-t18-pass-rates). Verdict:
  pass      both thresholds hold at the stated full scale;
  fail      they do not hold even at 4,000 candidates;
  unclear   they hold only at 4,000: the answer depends on a number the criterion does not fix -> the owner decides.
The estimate is share x candidates (point estimate, as the criterion says "estimated"); the Wilson interval is reported.
Criteria (b), (c), (d) are not computed here: (b) and (c) are test results, (d) is evidence from a Kaggle kernel log.
"""

import argparse
import json
from pathlib import Path

from eval.stats import wilson_ci
from training import config

UPPER_FULL_SCALE_N = (
    4000  # the upper end of the proposed sizing; only used to detect an "unclear" verdict
)


def criterion_a(tables: list[dict], full_scale: int = config.HARD_FULL_SCALE_N) -> dict:
    n = sum(t["summary"]["total"] for t in tables)
    k = sum(t["summary"]["kept"] for t in tables)
    share, lo, hi = wilson_ci(k, n)

    def holds(candidates: int) -> bool:
        return (
            share >= config.G3_MIN_IN_BAND_SHARE
            and share * candidates >= config.G3_MIN_IN_BAND_TASKS
        )

    verdict = "pass" if holds(full_scale) else "unclear" if holds(UPPER_FULL_SCALE_N) else "fail"
    return {
        "pilot_tasks": n,
        "in_band": k,
        "share": share,
        "share_ci95": [lo, hi],
        "share_threshold": config.G3_MIN_IN_BAND_SHARE,
        "share_ok": share >= config.G3_MIN_IN_BAND_SHARE,
        "full_scale_candidates": full_scale,
        "estimated_in_band_tasks": share * full_scale,
        "estimated_in_band_tasks_ci95": [lo * full_scale, hi * full_scale],
        "tasks_threshold": config.G3_MIN_IN_BAND_TASKS,
        "tasks_ok": share * full_scale >= config.G3_MIN_IN_BAND_TASKS,
        "estimated_at_upper_full_scale": share * UPPER_FULL_SCALE_N,
        "verdict": verdict,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = criterion_a([json.loads(p.read_text()) for p in a.tables])
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
