"""Parity of two systems/formats on the SAME tasks (EVALUATION §6, plan T22): how much does quantization cost?

`parity(a, b)` takes task_id -> success for each side. Reports agreement, both accuracies (Wilson), the
discordant pairs, an exact McNemar p-value and the paired-bootstrap difference. A difference that is small AND
whose interval contains 0 means the cheaper format can ship; the numbers decide, not an assumption.
"""

import json
from math import comb
from pathlib import Path

from eval.stats import paired_diff_ci, wilson_ci


def mcnemar_exact(n_ab: int, n_ba: int) -> float:
    n = n_ab + n_ba
    if n == 0:
        return 1.0
    k = min(n_ab, n_ba)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)


def parity(a: dict[str, bool], b: dict[str, bool]) -> dict:
    if set(a) != set(b):
        raise ValueError(
            "parity needs identical task sets on both sides (a missing task is a denominator bug)"
        )
    ids = sorted(a)
    n_ab = sum(a[i] and not b[i] for i in ids)  # a passes, b fails
    n_ba = sum(b[i] and not a[i] for i in ids)
    d, lo, hi = paired_diff_ci(b, a)
    return {
        "n": len(ids),
        "agreement": sum(a[i] == b[i] for i in ids) / len(ids),
        "a": wilson_ci(sum(a.values()), len(ids)),
        "b": wilson_ci(sum(b.values()), len(ids)),
        "only_a_passes": n_ab,
        "only_b_passes": n_ba,
        "mcnemar_p": mcnemar_exact(n_ab, n_ba),
        "b_minus_a": {"diff": d, "ci95": (lo, hi)},
    }


def load_results(run_dir: Path) -> dict[str, bool]:
    return {
        r["task_id"]: bool(r["success"])
        for r in map(json.loads, (run_dir / "results.jsonl").read_text().splitlines())
    }
