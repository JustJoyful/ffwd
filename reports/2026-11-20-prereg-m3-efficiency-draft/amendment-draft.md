# DRAFT (not final, not applied): preregistration amendment if M3 is trained, as an efficiency model

**Status: DRAFT for the owner's review.** `eval/PREREGISTRATION.md`, `config.PREREG_COMPARISONS` and the tests are NOT changed. It would be a dated amendment written before any test split is run and before any M3 checkpoint exists. It applies only if GRPO is run; the no-M3 draft (`reports/2026-11-20-prereg-no-m3-draft`) is the opposite case, and Variant B of it takes over if M3 fails the guard below.

## Why the question changes

M1 is 98% on dev; its room to improve is efficiency, not success. D-043 sets `spec_acc` weight 0 and targets what is left: needless re-encoding where a stream copy suffices (M1 dev: 8 of 31 copy-eligible tasks = 26% [14%, 43%], all 31 still passed) and extra runs (M1 dev: mean 1.135 runs per supported task; 267 of 289 needed one). So the preregistered M3-vs-M1 questions are no longer "does success go up on held-out splits" (Q3, Q5a, Q5b) but "does efficiency improve without losing success".

## Proposed text (to append to `eval/PREREGISTRATION.md` as a dated section)

> **Amendment (DATE): M3 targets efficiency (D-043).**
> 1. **Primary M3-vs-M1 endpoints** (replace Q3, Q5a, Q5b):
>    * **Q3a: needless-re-encode-or-fail rate on copy-eligible tasks**, pooled over test-iid and test-phrasing. A task is *copy-eligible* if it is not ambiguous or unsupported and its reference run is stream-copy only (`uses_stream_copy_only`; a property of the frozen task file, no model involved). Per task the outcome is 1 if the episode did not pass, or ran no command, or its final check reports `re_encoded` (the definition of `telemetry._needless_reencode`); else 0. Failures stay in the denominator, so an M3 that avoids re-encoding by failing gets no credit. Lower is better; the paired difference is M3 - M1.
>    * **Q3b: mean runs per supported task**, test-iid. Failed and no-run episodes count with the runs they used (0 if none). Lower is better; the paired difference is M3 - M1.
> 2. **Guard (not in Holm): success must not be worse by more than 2 points.** On the three generated splits pooled (test-iid + test-compositional + test-phrasing, n = 900), the one-sided 97.5% lower bound of the paired bootstrap difference in success (M3 - M1; 10,000 resamples, seed 20261115) must be above -2.0 pp. Per-split values are reported descriptively. The efficiency claim is made only if Q3a or Q3b is significant under Holm AND the guard is met (an intersection of conditions). If the guard is not met, M3 is reported as "guard not met", no efficiency claim is made, and the no-M3 amendment (Variant B) governs the confirmatory comparisons.
> 3. **Family.** Holm across exactly five comparisons (m = 5): Q2 (M1 - B2, test-iid, unchanged), Q3a, Q3b, Q4 (M3 - X1, test-iid success, unchanged), Q7 (M3 - B0, pooled test-real + test-phrasing success, unchanged). Q3, Q5a, Q5b are withdrawn (success M3 - M1 on test-iid, test-compositional, test-phrasing: now covered by the guard and descriptive tables).
> 4. `spec_acc` is not an endpoint. Spec accuracy and the real-spec-error rate on dev and on the test splits are reported descriptively for M1 and M3 (D-043: weight 0 gives no gradient on real spec errors, so a regression is possible and is shown, not tested).
> 5. All other numbers (per-split and per-family differences, the deduplicated test-iid subset of D-039, test-compositional for Q3a) are descriptive and outside Holm.

## How many copy-eligible tasks per test split (power inputs)

| set | tasks | copy-eligible | how known |
|---|---|---|---|
| dev | 300 | **31** (10.3%) | exact |
| train | 4,472 renderings = 1,500 unique contents | **688 renderings = 232 contents** (15.4% of renderings, 15.5% of contents) | exact |
| test-iid | 500 | about **52 to 77** | estimated from the dev and train rates, test file **not read** |
| test-phrasing | 200 | about **21 to 31** | same |
| test-compositional | 200 | about **21 to 31** (descriptive only) | same |
| test-real | about 100 | unknown (your requests; depends on which clips and chores) | not yet written |

Pooled Q3a population (test-iid + test-phrasing): about **73 to 108** tasks. The exact counts require reading the test task files (counts only; no contents shown, no system run). I did not do that; it is one command and I will run it only if you say so. The dev and train rates differ (10.3% vs 15.5% of contents; about 3 standard errors), which I have not explained: both come from the same generator, so it may be chance in the hash buckets, or a property of dev I should look at.

## Power (paired normal approximation, 80%, two-sided, Holm worst case alpha = 0.05 / 5; "disagree" is an assumed share of tasks where M1 and M3 differ)

* **Q3a**, n = 80 / 110: detectable difference **21 / 18 pp at 30% disagreement** (17 / 15 pp at 20%). With M1 at about 26%, only a near-elimination of needless re-encoding (to about 5% or less) would be detected. A smaller real improvement would be reported as not significant.
* **Q3b**, n about 450 supported test-iid tasks, assumed sd of the per-task difference 0.3 to 0.5 runs: detectable **0.05 to 0.08 runs**. M1's dev mean is 1.135, so the most M3 could gain is about 0.13: this endpoint can only confirm a large share of the possible improvement.
* **Guard**, n = 900, margin 2 pp: power to show non-inferiority when the true difference is 0 is **93%** (3% of tasks disagreeing), **77%** (5%), **56%** (8%); at a true -0.5 pp and 3% disagreement, 74%. (On test-iid alone, n = 500, those are 73%, 52%, 35%: the pooled guard is the better choice.) A guard that is not met because of low power is not evidence of harm; the rule above still treats it as "not met", on purpose.

## What would be changed in the repo if you finalise (not done)

* `eval/PREREGISTRATION.md`: the dated section above; `training/config.py` `PREREG_COMPARISONS` to the five comparisons (Q2, Q3a, Q3b, Q4, Q7) plus a separate constant for the guard (margin 2 pp, pooled splits); `tests/eval/test_final_report.py:130` updated in the same commit.
* `eval/final_report.py` does not yet compute Q3a, Q3b or the guard: it needs the per-episode `last_check.measurements.re_encoded` and `runs` (both are in `episodes.jsonl` already) and the copy-eligible flag from the task file. To build and test on dev before any test run.
* The preregistration section on GRPO stopping rules and the shuffled-reward control stays; the control's pass rule is unchanged (dev success not above M1 beyond its CI and format validity holds).

## For you to decide

1. Guard on the pooled three generated splits (my proposal) or on test-iid only.
2. Q3a pooled over test-iid + test-phrasing (my proposal; larger n) or test-iid only.
3. Whether I may run the counts-only script on the test task files, or you prefer to keep them unread until the freeze.
4. Whether to keep Q4 and Q7 as success comparisons for M3, given M3 is expected to be about as successful as M1 (they remain valid questions about the final system).
5. The unexplained dev vs train copy-eligible share.


---
**Superseded (20 Nov 2026) by `amendment-draft-v2.md`:** Holm over m = 5 is replaced by a fixed-sequence procedure at alpha 0.05 (Q2, Q7, Q3a, Q3b, Q4), the guard and Q3a are pooled as decided, the exact test counts replace the estimates, and the power table is recomputed. This file is kept as written.
