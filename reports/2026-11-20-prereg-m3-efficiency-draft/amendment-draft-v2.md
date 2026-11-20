# DRAFT v2 (not final, not applied): preregistration amendment if M3 is trained, as an efficiency model

**Status: DRAFT for the owner's approval before FINAL.** Supersedes `amendment-draft.md` (v1, kept unchanged). `eval/PREREGISTRATION.md`, `config.PREREG_COMPARISONS` and the tests are NOT changed. It would be a dated amendment written before any test split is run and before any M3 checkpoint exists. It applies only if GRPO is run; if M3 fails the guard, or is not trained, the no-M3 amendment (Variant B, `reports/2026-11-20-prereg-no-m3-draft`) governs.

Decisions folded in (owner, 20 Nov 2026): guard pooled; Q3a pooled; the copy-share gap between train and dev is reported only; a FIXED-SEQUENCE procedure at alpha = 0.05 replaces Holm; exact test counts were run (counts only, `reports/2026-11-20-test-counts/`).

## Proposed text (to append to `eval/PREREGISTRATION.md` as a dated section)

> **Amendment (DATE): M3 targets efficiency (D-043).**
> 1. **Endpoints.** The confirmatory comparisons are exactly these five, in this order:
>    1. **Q2**: M1 - B2, success on test-iid (unchanged).
>    2. **Q7**: M3 - B0, success on test-real + test-phrasing pooled (unchanged).
>    3. **Q3a**: M3 - M1, **needless-re-encode-or-fail rate on copy-eligible tasks**, pooled over test-iid, test-phrasing and test-real. A task is *copy-eligible* if it is not ambiguous or unsupported and its reference run is stream-copy only (`uses_stream_copy_only`; a property of the frozen task file). Per task the outcome is 1 if the episode did not pass, or ran no command, or its final check reports `re_encoded` (the definition of `telemetry._needless_reencode`); else 0. Failures stay in the denominator. Lower is better.
>    4. **Q3b**: M3 - M1, **mean runs per supported task**, test-iid (failed and no-run episodes count with the runs they used). Lower is better.
>    5. **Q4**: M3 - X1, success on test-iid (unchanged).
> 2. **Procedure: fixed sequence at alpha = 0.05 (two-sided, paired bootstrap, 10,000 resamples, seed 20261115).** Test in the order above. Each comparison is tested at 0.05 only if every earlier one rejected its null; at the first non-rejection the procedure stops and every later comparison is reported as descriptive (no p-value is claimed). This controls the family-wise error rate at 0.05 with no alpha split, **because the order is fixed here, before any result**. Holm is no longer used for this family. Q3, Q5a and Q5b (success M3 - M1 per split) are withdrawn.
> 3. **Guard (a condition on the efficiency claim, not a test in the sequence):** on the three generated splits pooled (test-iid + test-compositional + test-phrasing, n = 900) the one-sided 97.5% lower bound of the paired bootstrap difference in success (M3 - M1) must be above -2.0 pp. The efficiency claim (Q3a or Q3b rejected) is made only if the guard is met. If it is not met, M3 is reported as "guard not met" with no efficiency claim and the no-M3 amendment governs. Per-split success differences are descriptive.
> 4. `spec_acc` is not an endpoint. The material spec error rate (`eval/spec_errors.py`) and the spec accuracy are reported for every system on dev and test, descriptively, as a drift watch for M3 vs M1.
> 5. Everything else (per-split and per-family differences, the deduplicated test-iid subset of D-039, Q3a restricted to test-iid, test-compositional) is descriptive.

## Exact counts (counts-only run, no outcomes, no system; `reports/2026-11-20-test-counts/`)

| split | tasks | graded | copy-eligible |
|---|---|---|---|
| test-iid | 500 | 458 | **55** |
| test-iid, deduplicated subset (D-039) | 396 | 381 | **36** |
| test-phrasing | 200 | 176 | **35** |
| test-compositional | 200 | 200 | **0** |
| test-real | about 100 | about 100 | about 30 or more, if the test-real README guidance is followed (not yet written) |

Pooled Q3a population: **55 + 35 = 90** from the generated splits, **about 120 or more with test-real**. test-compositional has no copy-eligible task, so Q3a cannot be measured there (nothing to report: the held-out combinations contain no stream-copy-possible chore). The copy-eligible share differs between train (15.5% of contents), dev (10.3%) and the test splits (11% of test-iid tasks, 17.5% of test-phrasing tasks): reported only, not investigated (owner decision).

## Power table for the fixed sequence (paired normal approximation, 80%, two-sided, alpha 0.05 for each step reached; "disagree" = assumed share of tasks where the two systems differ). Differences in percentage points unless stated

| step | comparison | n | disagree | detectable difference |
|---|---|---|---|---|
| 1 | Q2 M1 - B2, test-iid | 500 | 40% / 60% | 7.9 / 9.7 (the expected effect is far larger: B0 was 59% and the stock model 0% on dev) |
| 2 | Q7 M3 - B0, test-real + test-phrasing | about 300 | 30% / 50% | 8.9 / 11.4 (expected effect large) |
| 3 | Q3a, copy-eligible, generated splits only | 90 | 20% / 30% / 40% | **13.2 / 16.2 / 18.7** |
| 3 | Q3a, with about 30 test-real copy-eligible | about 120 | 20% / 30% / 40% | **11.4 / 14.0 / 16.2** |
| 4 | Q3b mean runs per supported task, test-iid | 458 | sd of the per-task difference 0.3 / 0.4 / 0.5 runs | **0.039 / 0.052 / 0.065 runs** |
| 5 | Q4 M3 - X1, test-iid | 500 | 15% / 30% | 4.9 / 6.9 |
| guard | success M3 - M1, three generated splits | 900 | 3% / 5% / 8% | power to show non-inferiority at true difference 0: 93% / 77% / 56% |

What changed against v1 (Holm, m = 5): each step now uses alpha 0.05 instead of 0.01 to 0.05, so the detectable differences shrink (Q3a n = 90 at 30% disagreement: 16.2 pp now, against about 20 pp under Holm's worst-case alpha 0.01); the cost is the dependency below. M1's dev needless-re-encode rate is 26%, so Q3a still needs a large effect (to about 10% or less) to be detected; Q3b can detect 0.04 to 0.07 runs against a maximum possible gain of about 0.13.

## What the fixed sequence costs (so it is approved with open eyes)

* **Q3a and Q3b (the point of GRPO) are only tested if Q2 and Q7 reject.** Q2 will, with near certainty. Q7 includes test-real (about 100 requests, not yet written): if M3 is not significantly better than the rule-based baseline B0 on real plus re-phrased requests, the efficiency endpoints become descriptive even if M3 is clearly more efficient than M1. B0 scored 59% on dev against M1's 98%, so a failure here would itself be a headline finding; but it is the one place the order can bite.
* **Q4 is last and descriptive unless everything before it rejected.** It is the least important for the efficiency claim, which is why it is last.
* The guard is not a step, so a guard failure does not stop Q4; it removes the efficiency claim.

## What would be changed in the repo if you finalise (not done)

* `eval/PREREGISTRATION.md`: the dated section above; `training/config.py` `PREREG_COMPARISONS` replaced by the ordered five (and a `PREREG_PROCEDURE = "fixed-sequence"` note), plus a constant for the guard (margin 2 pp, pooled generated splits); `tests/eval/test_final_report.py:130` updated in the same commit.
* `eval/final_report.py`: stop applying Holm to this family and implement the ordered procedure (stop at the first non-rejection; later rows labelled descriptive), Q3a and Q3b and the guard (per-episode `last_check.measurements.re_encoded`, `runs`, and the copy-eligible flag from the task file). To build and test on dev before any test run.
* The GRPO stopping rules and the shuffled-reward control stay unchanged.

## Still open for your approval

1. Q3a pooled over test-iid + test-phrasing + test-real (my reading of "Q3a pooled" together with the new test-real copy-eligible guidance), or generated splits only.
2. The order itself (Q2, Q7, Q3a, Q3b, Q4) is yours; I only note that it puts the efficiency claim behind Q7.
