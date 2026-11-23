# Phase 1 results

Wilson 95% CIs; failed, timed-out, malformed and errored episodes count as failures.

| System | test-compositional | test-iid | test-phrasing | test-iid (dedup) | runs/task (iid) | re-encode rate |
|---|---|---|---|---|---|---|
| B0 | 125/200 = 62% [56%, 69%] | 281/500 = 56% [52%, 60%] | 129/200 = 64% [58%, 71%] | 212/396 = 54% [49%, 58%] | 0.87 | 7% |
| B2 | 0/200 = 0% [0%, 2%] | 0/500 = 0% [0%, 1%] | 0/200 = 0% [0%, 2%] | 0/396 = 0% [0%, 1%] | 0.00 | n/a |
| M1 | 194/200 = 97% [94%, 99%] | 485/500 = 97% [95%, 98%] | 187/200 = 94% [89%, 96%] | 383/396 = 97% [94%, 98%] | 1.05 | 9% |
| M3 | 194/200 = 97% [94%, 99%] | 485/500 = 97% [95%, 98%] | 188/200 = 94% [90%, 97%] | 385/396 = 97% [95%, 98%] | 1.03 | 2% |
| X1 | 195/200 = 98% [94%, 99%] | 483/500 = 97% [95%, 98%] | 188/200 = 94% [90%, 97%] | 382/396 = 96% [94%, 98%] | 0.99 | 9% |

## Material spec error rate (container, resolution, time range, lossless, requested codec; lower is better)

| System | test-compositional | test-iid | test-phrasing |
|---|---|---|---|
| B0 | n/a (emits no spec) | n/a (emits no spec) | n/a (emits no spec) |
| B2 | n/a (emits no spec) | n/a (emits no spec) | n/a (emits no spec) |
| M1 | 34/200 = 17% [12%, 23%] | 107/439 = 24% [21%, 29%] | 42/171 = 25% [19%, 32%] |
| M3 | 28/200 = 14% [10%, 19%] | 97/439 = 22% [18%, 26%] | 38/171 = 22% [17%, 29%] |
| X1 | 20/200 = 10% [7%, 15%] | 91/439 = 21% [17%, 25%] | 31/171 = 18% [13%, 25%] |

## Preregistered comparisons (fixed-sequence, alpha 0.05; b - a, paired bootstrap; lower is better for runs and needless-or-fail)

| Comparison | split | n | diff [95% CI] | raw p | status |
|---|---|---|---|---|---|
| Q2 M1-B2 | test-iid | 500 | +97.000 pp [+95.400, +98.400] | 0.0001 | rejected |
| Q7 M3-B0 | test-phrasing | 200 | +29.500 pp [+22.500, +36.500] | 0.0001 | rejected |
| Q3a M3-M1 needless-or-fail | test-iid+test-phrasing | 90 | -11.111 pp [-18.889, -4.444] | 0.0010 | rejected |
| Q3b M3-M1 runs | test-iid | 458 | -0.024 [-0.061, +0.011] | 0.1982 | NOT rejected: sequence stops |
| Q4 M3-X1 | test-iid | 500 | +0.400 pp [-1.600, +2.400] | - | descriptive (after the stop) |

Guard (M3 - M1 success, test-iid+test-compositional+test-phrasing): +0.11 pp, one-sided 97.5% lower bound -0.89 pp against -2.0 pp: **met**. Efficiency claim: **yes** (needs Q3b or Q3a rejected AND the guard met).

Descriptive only (outside the sequence): pooled comparisons split by component; test-iid comparisons on the deduplicated subset (pp for rates, runs for Q3b).

| Comparison | split | diff [95% CI] |
|---|---|---|
| Q2 M1-B2 | test-iid (dedup) | +96.717 [+94.949, +98.232] |
| Q3a M3-M1 needless-or-fail | test-iid | -7.273 [-16.364, +0.000] |
| Q3a M3-M1 needless-or-fail | test-phrasing | -17.143 [-31.429, -5.714] |
| Q3b M3-M1 runs | test-iid (dedup) | -0.034 [-0.073, +0.003] |
| Q4 M3-X1 | test-iid (dedup) | +0.758 [-1.515, +3.030] |

Single training seed: differences between M-systems reflect one run each.

See `by_family.csv` for per-family and per-difficulty results.
