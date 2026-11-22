# Phase 1 results

Wilson 95% CIs; failed, timed-out, malformed and errored episodes count as failures.

| System | test-compositional | test-iid | test-phrasing | runs/task (iid) | re-encode rate |
|---|---|---|---|---|---|
| B0 | 5/10 = 50% [24%, 76%] | 5/10 = 50% [24%, 76%] | 5/10 = 50% [24%, 76%] | 0.90 | 0% |
| B2 | 0/10 = 0% [0%, 28%] | 0/10 = 0% [0%, 28%] | 0/10 = 0% [0%, 28%] | 0.00 | n/a |
| M1 | 10/10 = 100% [72%, 100%] | 10/10 = 100% [72%, 100%] | 10/10 = 100% [72%, 100%] | 0.90 | 100% |
| M3 | 10/10 = 100% [72%, 100%] | 10/10 = 100% [72%, 100%] | 10/10 = 100% [72%, 100%] | 0.90 | 0% |
| X1 | 10/10 = 100% [72%, 100%] | 10/10 = 100% [72%, 100%] | 10/10 = 100% [72%, 100%] | 0.90 | 100% |

## Material spec error rate (container, resolution, time range, lossless, requested codec; lower is better)

| System | test-compositional | test-iid | test-phrasing |
|---|---|---|---|
| B0 | n/a (emits no spec) | n/a (emits no spec) | n/a (emits no spec) |
| B2 | n/a (emits no spec) | n/a (emits no spec) | n/a (emits no spec) |
| M1 | 4/9 = 44% [19%, 73%] | 4/9 = 44% [19%, 73%] | 4/9 = 44% [19%, 73%] |
| M3 | 3/9 = 33% [12%, 65%] | 3/9 = 33% [12%, 65%] | 3/9 = 33% [12%, 65%] |
| X1 | 1/9 = 11% [2%, 43%] | 1/9 = 11% [2%, 43%] | 1/9 = 11% [2%, 43%] |

## Preregistered comparisons (fixed-sequence, alpha 0.05; b - a, paired bootstrap; lower is better for runs and needless-or-fail)

| Comparison | split | n | diff [95% CI] | raw p | status |
|---|---|---|---|---|---|
| Q2 M1-B2 | test-iid | 10 | +100.000 pp [+100.000, +100.000] | 0.0001 | rejected |
| Q7 M3-B0 | test-phrasing | 10 | +50.000 pp [+20.000, +80.000] | 0.0020 | rejected |
| Q3a M3-M1 needless-or-fail | test-iid+test-phrasing | 6 | -100.000 pp [-100.000, -100.000] | 0.0001 | rejected |
| Q3b M3-M1 runs | test-iid | 9 | +0.000 [+0.000, +0.000] | 1.0000 | NOT rejected: sequence stops |
| Q4 M3-X1 | test-iid | 10 | +0.000 pp [+0.000, +0.000] | - | descriptive (after the stop) |

Guard (M3 - M1 success, test-iid+test-compositional+test-phrasing): +0.00 pp, one-sided 97.5% lower bound +0.00 pp against -2.0 pp: **met**. Efficiency claim: **yes** (needs Q3b or Q3a rejected AND the guard met).

Descriptive only (outside the sequence): pooled comparisons split by component; test-iid comparisons on the deduplicated subset (pp for rates, runs for Q3b).

| Comparison | split | diff [95% CI] |
|---|---|---|
| Q3a M3-M1 needless-or-fail | test-iid | -100.000 [-100.000, -100.000] |
| Q3a M3-M1 needless-or-fail | test-phrasing | -100.000 [-100.000, -100.000] |

Single training seed: differences between M-systems reflect one run each.

See `by_family.csv` for per-family and per-difficulty results.
