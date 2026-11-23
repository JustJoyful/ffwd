# Phase 1 browser row (Amendment 4): M3 Q5_K_M in the browser (wllama), extra row, descriptive

M3 Q8_0 stays the headline model. No p-values and no efficiency claim are made for this row. Failed, errored and context-ended episodes count as failures.

| System | test-iid | test-phrasing | test-compositional |
|---|---|---|---|
| M3-browser | 483/500 = 96.6% [94.6%, 97.9%] | 181/200 = 90.5% [85.6%, 93.8%] | 191/200 = 95.5% [91.7%, 97.6%] |
| M3 | 485/500 = 97.0% [95.1%, 98.2%] | 188/200 = 94.0% [89.8%, 96.5%] | 194/200 = 97.0% [93.6%, 98.6%] |
| M1 | 485/500 = 97.0% [95.1%, 98.2%] | 187/200 = 93.5% [89.2%, 96.2%] | 194/200 = 97.0% [93.6%, 98.6%] |
| X1 | 483/500 = 96.6% [94.6%, 97.9%] | 188/200 = 94.0% [89.8%, 96.5%] | 195/200 = 97.5% [94.3%, 98.9%] |

## Primary (descriptive) and guard

Paired success difference M3-browser minus M3, three splits pooled (n = 900): **-1.33 pp** (95% CI [-2.67, -0.11] pp).
Guard (Amendment 3 item 5 reused): one-sided 97.5% lower bound -2.67 pp against -2.0 pp: **NOT shown**.

| Split | n | diff | 95% CI (pp) |
|---|---|---|---|
| test-iid | 500 | -0.40 pp | [-2.00, +1.20] |
| test-phrasing | 200 | -3.50 pp | [-7.00, -0.50] |
| test-compositional | 200 | -1.50 pp | [-4.50, +1.50] |

## Context only (not part of any claim)

- M3-browser minus M1 on test-iid, test-phrasing, test-compositional: -1.22 pp [-2.56, +0.00] pp (n = 900)
- M3-browser minus X1 on test-iid, test-phrasing, test-compositional: -1.22 pp [-3.11, +0.56] pp (n = 900)

Needless-re-encode-or-fail on copy-eligible tasks (test-iid, test-phrasing, n = 90; lower is better): browser 5.6%, M3 4.4%, difference +1.11 pp [-4.44, +6.67].

## Episodes that did not complete normally

Invalid-action episodes: M3-browser 2; M3 5; M1 3; X1 221.
Ended by the context rule (prompt + 512-token reply budget would not fit in n_ctx 8192, counted as not done): test-iid 0, test-phrasing 0, test-compositional 0.
Other infrastructure errors (counted as failures): test-iid 0, test-phrasing 0, test-compositional 0.

## Material spec error rate (descriptive; lower is better)

- M3-browser: test-iid 97/439 = 22% [18%, 26%]; test-phrasing 39/171 = 23% [17%, 30%]; test-compositional 26/200 = 13% [9%, 18%]
- M3: test-iid 97/439 = 22% [18%, 26%]; test-phrasing 38/171 = 22% [17%, 29%]; test-compositional 28/200 = 14% [10%, 19%]

## Latency (bridge log; one laptop, nothing else heavy running)

| Split | turns | median | p90 | max | prompt tok/s | generation tok/s |
|---|---|---|---|---|---|---|
| test-iid | 1463 | 2.13 s | 3.92 s | 20.1 s | 194 | 53.6 |
| test-phrasing | 592 | 2.19 s | 4.14 s | 21.7 s | 180 | 52.2 |
| test-compositional | 625 | 2.36 s | 3.52 s | 6.5 s | 199 | 53.4 |

One laptop (RTX 3050 6 GB), one Chromium build, one seed: this row describes that configuration, not the field. Its runtime build (wllama's llama.cpp) differs from the native one used for the other rows.
