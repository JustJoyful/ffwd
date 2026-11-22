"""Statistics (EVALUATION §5): Wilson intervals for single success rates (D-021), paired percentile
bootstrap for system-vs-system differences on the same tasks."""

import random
from math import sqrt
from statistics import NormalDist

from training import config


def _percentiles(samples: list[float]) -> tuple[float, float]:
    s = sorted(samples)
    return s[int(0.025 * (len(s) - 1))], s[int(0.975 * (len(s) - 1))]


def wilson_ci(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float, float]:
    """Wilson score interval for a success rate: (rate, low, high). Unlike the percentile bootstrap it
    does not collapse to [0, 0] at 0/n or [1, 1] at n/n (D-021)."""
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError(f"need 0 <= successes <= n and n > 0, got {successes}/{n}")
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def paired_diff_ci(
    a: dict[str, float],
    b: dict[str, float],
    resamples: int = config.BOOTSTRAP_RESAMPLES,
    seed: int = config.BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """Mean of (a − b) over the same tasks, resampling tasks jointly. Task sets must match exactly:
    a missing task is a denominator problem to fix, not to paper over."""
    if set(a) != set(b):
        raise ValueError(f"task sets differ: {sorted(set(a) ^ set(b))[:5]}")
    diffs = [float(a[k]) - float(b[k]) for k in sorted(a)]
    n, rng = len(diffs), random.Random(seed)
    means = [sum(rng.choices(diffs, k=n)) / n for _ in range(resamples)]
    return (sum(diffs) / n, *_percentiles(means))


def paired_diff_pvalue(
    a: dict[str, float],
    b: dict[str, float],
    resamples: int = config.BOOTSTRAP_RESAMPLES,
    seed: int = config.BOOTSTRAP_SEED,
) -> float:
    """Two-sided bootstrap p for "mean(a - b) = 0": 2 * min(P(resampled mean <= 0), P(>= 0)), floored at 1/resamples."""
    if set(a) != set(b):
        raise ValueError(f"task sets differ: {sorted(set(a) ^ set(b))[:5]}")
    diffs = [float(a[k]) - float(b[k]) for k in sorted(a)]
    n, rng = len(diffs), random.Random(seed)
    means = [sum(rng.choices(diffs, k=n)) / n for _ in range(resamples)]
    le, ge = sum(m <= 0 for m in means) / resamples, sum(m >= 0 for m in means) / resamples
    return min(1.0, max(2 * min(le, ge), 1 / resamples))


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni adjusted p-values (step-down), in the same keys."""
    order = sorted(pvalues, key=pvalues.get)
    m, running, out = len(order), 0.0, {}
    for i, k in enumerate(order):
        running = max(running, (m - i) * pvalues[k])
        out[k] = min(1.0, running)
    return out


def detectable_difference(
    n: int, discordant_rate: float, alpha: float = 0.05, power: float = 0.8
) -> float:
    """Smallest true paired difference (as a rate) a two-sided test at `alpha` detects with `power`, for n tasks
    on which the two systems disagree on a fraction `discordant_rate` of tasks. Normal approximation of the paired
    difference: var(d) ~= discordant_rate / n for small d. Under Holm the strictest step uses alpha / m, so pass
    alpha / m for the worst case. This is a planning figure under stated assumptions, not a result.
    """
    if n <= 0 or not 0 < discordant_rate <= 1:
        raise ValueError("need n > 0 and 0 < discordant_rate <= 1")
    z = NormalDist().inv_cdf
    return (z(1 - alpha / 2) + z(power)) * sqrt(discordant_rate / n)
