"""Bootstrap statistics (EVALUATION §5): percentile 95% CIs, paired bootstrap for system vs system."""

import random

from training import config


def _percentiles(samples: list[float]) -> tuple[float, float]:
    s = sorted(samples)
    return s[int(0.025 * (len(s) - 1))], s[int(0.975 * (len(s) - 1))]


def bootstrap_ci(
    successes: list[bool],
    resamples: int = config.BOOTSTRAP_RESAMPLES,
    seed: int = config.BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    xs = [float(x) for x in successes]
    n, rng = len(xs), random.Random(seed)
    means = [sum(rng.choices(xs, k=n)) / n for _ in range(resamples)]
    return (sum(xs) / n, *_percentiles(means))


def paired_diff_ci(
    a: dict[str, bool],
    b: dict[str, bool],
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
