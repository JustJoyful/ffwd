# DRAFT v3 (not final, not applied): preregistration amendment if M3 is trained, as an efficiency model

**Status: DRAFT for the owner's approval before FINAL.** Supersedes v2 (`amendment-draft-v2.md`) and v1; both are kept unchanged. `eval/PREREGISTRATION.md`, `config.PREREG_COMPARISONS` and the tests are NOT changed. It would be a dated amendment written before any test split is run and before any M3 checkpoint exists. It applies only if GRPO produces an M3; if M3 fails the guard, or is not trained, the no-M3 amendment (Variant B, `reports/2026-11-20-prereg-no-m3-draft`) governs.

What changed against v2 (owner, 21 Nov 2026): the order is now **Q2 -> Q7 -> Q3b -> Q3a -> Q4** (runs before re-encode); Q3a pools test-real (as v2 proposed, now decided); the power table is recomputed for the new order.

## Why runs before re-encode (from the train-side pool, `reports/2026-11-20-grpo-pool/`)
The GRPO pool shows where the training signal is: **runs differ among passed samples in 187 groups; needless re-encode differs in only 48 groups, 37 unique contents** (of 358 prompts, 249 unique contents). GRPO has far more to learn about the number of runs than about avoiding re-encodes, so Q3b (runs) is the endpoint M3 is most likely to move and goes first; Q3a (re-encode), the thinner lever, goes after it. The ordering is justified by training-side data only; no test outcome informed it.

## Proposed text (to append to `eval/PREREGISTRATION.md` as a dated section)

> **Amendment (DATE): M3 targets efficiency (D-043, D-045).**
> 1. **Endpoints.** The confirmatory comparisons are exactly these five, in this order:
>    1. **Q2**: M1 - B2, success on test-iid (unchanged).
>    2. **Q7**: M3 - B0, success on test-real + test-phrasing pooled (unchanged).
>    3. **Q3b**: M3 - M1, **mean runs per supported task**, test-iid. Failed and no-run episodes count with the runs they used (0 if none). Lower is better.
>    4. **Q3a**: M3 - M1, **needless-re-encode-or-fail rate on copy-eligible tasks**, pooled over test-iid, test-phrasing and test-real. A task is *copy-eligible* if it is not ambiguous or unsupported and its reference run is stream-copy only (`uses_stream_copy_only`; a property of the frozen task file). Per task the outcome is 1 if the episode did not pass, or ran no command, or its final check reports `re_encoded` (the definition of `telemetry._needless_reencode`); else 0. Failures stay in the denominator. Lower is better.
>    5. **Q4**: M3 - X1, success on test-iid (unchanged).
> 2. **Procedure: fixed sequence at alpha = 0.05 (two-sided, paired bootstrap, 10,000 resamples, seed 20261115).** Test in the order above. Each comparison is tested at 0.05 only if every earlier one rejected its null; at the first non-rejection the procedure stops and every later comparison is reported as descriptive (no p-value is claimed). This controls the family-wise error rate at 0.05 with no alpha split, **because the order is fixed here, before any result**. Holm is not used for this family. Q3, Q5a and Q5b (success M3 - M1 per split) are withdrawn.
> 3. **Guard (a condition on the efficiency claim, not a test in the sequence):** on the three generated splits pooled (test-iid + test-compositional + test-phrasing, n = 900) the one-sided 97.5% lower bound of the paired bootstrap difference in success (M3 - M1) must be above -2.0 pp. The efficiency claim (Q3b or Q3a rejected) is made only if the guard is met. If it is not met, M3 is reported as "guard not met" with no efficiency claim and the no-M3 amendment governs. Per-split success differences are descriptive.
> 4. `spec_acc` is not an endpoint. The material spec error rate (`eval/spec_errors.py`) and the spec accuracy are reported for every system on dev and test, descriptively, as a drift watch for M3 vs M1.
> 5. Everything else (per-split and per-family differences, the deduplicated test-iid subset of D-039, Q3a restricted to test-iid, test-compositional) is descriptive.

## Exact counts (counts-only run, no outcomes, no system; `reports/2026-11-20-test-counts/`)

| split | tasks | graded | copy-eligible |
|---|---|---|---|
| test-iid | 500 | 458 | **55** |
| test-iid, deduplicated subset (D-039) | 396 | 381 | **36** |
| test-phrasing | 200 | 176 | **35** |
| test-compositional | 200 | 200 | **0** |
| test-real | about 100 | about 100 | **about 30 or more** if the README guidance is followed (not yet written) |

Q3a population: **55 + 35 = 90 from the generated splits, about 120 or more with test-real.** test-compositional has no copy-eligible task, so Q3a is not measurable there. The copy-eligible share differs between train (15.5% of contents), dev (10.3%), test-iid (11%) and test-phrasing (17.5%): reported only, not investigated.

## Power table for the fixed sequence (paired normal approximation, 80%, two-sided, alpha 0.05 at each step reached; "disagree" = assumed share of tasks where the two systems differ). Percentage points unless stated

| step | comparison | n | disagree | detectable difference |
|---|---|---|---|---|
| 1 | Q2 M1 - B2, test-iid | 500 | 40% / 60% | 7.9 / 9.7 (the expected effect is far larger: stock 0.6B scored 0/300 on dev) |
| 2 | Q7 M3 - B0, test-real + test-phrasing | about 300 | 30% / 50% | 8.9 / 11.4 (expected effect large: B0 59% vs M1 98% on dev) |
| 3 | **Q3b** mean runs per supported task, test-iid | 458 | sd of the per-task difference 0.3 / 0.4 / 0.5 runs | **0.039 / 0.052 / 0.065 runs** |
| 4 | **Q3a** copy-eligible, generated splits only | 90 | 20% / 30% / 40% | **13.2 / 16.2 / 18.7** |
| 4 | **Q3a** with about 30 test-real copy-eligible | about 120 | 20% / 30% / 40% | **11.4 / 14.0 / 16.2** |
| 5 | Q4 M3 - X1, test-iid | 500 | 15% / 30% | 4.9 / 6.9 |
| guard | success M3 - M1, three generated splits | 900 | 3% / 5% / 8% | power to show non-inferiority at true difference 0: 93% / 77% / 56% |

The power per step is the same as in v2: only the order changed. What the order changes is **which endpoint depends on which**:

* **Q3b now gates Q3a.** Q3b can only detect 0.04 to 0.065 runs, and M1's dev mean is 1.135, so the most M3 can gain is about 0.13: Q3b rejects only if M3 removes roughly a third to a half of M1's excess runs. If it does not, **Q3a is reported descriptively even if M3 cut needless re-encoding sharply.** The pool says runs is where the learnable signal is, which is why this order is the better bet, but it is a real cost to the re-encode claim (Q3a's own n is about 90 to 120, so it needs a drop from M1's 26% to about 10% or less to be detected in any case).
* Q2 and Q7 gate both: Q2 will reject with near certainty; Q7 includes test-real (about 100 requests, not yet written). If M3 is not significantly better than B0 on real plus re-phrased requests, both efficiency endpoints are descriptive. B0 scored 59% on dev against M1's 98%, so that would itself be a headline finding.
* Q4 is last and is tested only if everything before it rejected. The guard is not a step: a guard failure removes the efficiency claim but does not stop Q4.

## What would be changed in the repo if you finalise (not done)

* `eval/PREREGISTRATION.md`: the dated section above; `training/config.py` `PREREG_COMPARISONS` replaced by the ordered five (Q2, Q7, Q3b, Q3a, Q4) plus `PREREG_PROCEDURE = "fixed-sequence"` and a guard constant (margin 2 pp, pooled generated splits); `tests/eval/test_final_report.py:130` updated in the same commit.
* `eval/final_report.py`: stop applying Holm to this family and implement the ordered procedure (stop at the first non-rejection; later rows labelled descriptive), Q3b, Q3a and the guard (per-episode `runs`, `last_check.measurements.re_encoded`, and the copy-eligible flag from the task file; the material spec error rate table is already in). To build and test on dev before any test run.
* The GRPO stopping rules and the shuffled-reward control stay unchanged.

## Still open for your approval
1. The order is now yours and recorded (Q2, Q7, Q3b, Q3a, Q4). Nothing else is open in this draft except the usual FINAL approval.
