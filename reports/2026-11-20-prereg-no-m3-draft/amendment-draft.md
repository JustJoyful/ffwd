# DRAFT (not final, not applied): preregistration amendment if M3 is not trained

**Status: DRAFT for the owner. `eval/PREREGISTRATION.md`, `config.PREREG_COMPARISONS` and the tests are NOT changed.** Nothing here is in force until you finalise it. It would be a dated amendment written before any test split is run and before any M3 exists.

## Proposed text (to append to `eval/PREREGISTRATION.md` as a dated section)

> **Amendment (DATE): M3 not trained; see D-040.**
> The multi-turn GRPO model M3 was not trained (D-040: on the train distribution M1 passes 73-81% of tasks 8/8 at temperature 1.0 and only 8.8% of pilot tasks are in the 20-80% band; the owner did not approve the scale-up). This amendment is made before any test split has been run and before any M3 checkpoint exists. Dev results are known (M1 98% [95, 99], "SFT nearly sufficient" per the SFT-to-GRPO rule above).
> 1. **Systems.** The results table lists M3 as "not trained; see D-040", with no row of numbers. No checkpoint selection takes place. The shuffled-reward control and the "50 random passed M3 outputs" inspection do not apply.
> 2. **Primary comparison family.** Every comparison that involves M3 (Q3, Q4, Q5a, Q5b, Q7 as written) is withdrawn, not replaced silently. The family is the one chosen in the variants below.
> 3. **Holm** is applied across exactly the comparisons of the chosen family, with m = its size, using the same step-down procedure (`eval.stats.holm`), paired bootstrap (10,000 resamples, seed 20261115), and the same 5-point minimum meaningful difference.
> 4. All other numbers (per-split, per-family, M1 vs any system not in the family, the test-iid deduplicated subset, D-039) are descriptive, labelled as such, with Wilson 95% intervals, and are outside Holm.
> 5. The sections of this document that refer to M3 (systems list, family, "GRPO stopping rules", the shuffled-control paragraph) are inactive; no threshold that remains in force changes.

## Variants of the family (you choose one)

| | Variant A: strict reduction | Variant B: M1 takes M3's place (my recommendation) |
|---|---|---|
| Comparisons | Q2: M1 - B2 on test-iid | Q2: M1 - B2 on test-iid; Q4': M1 - X1 on test-iid; Q7': M1 - B0 pooled over test-real + test-phrasing |
| m | 1 | 3 |
| Holm | adjusted p = raw p, alpha 0.05 | smallest raw p x 3, next x 2, largest x 1 (step-down, monotone); equivalent thresholds 0.0167 / 0.025 / 0.05 |
| What is lost | every confirmatory claim except "M1 beats the untuned base on the training distribution" (a very large effect: stock 0.6B scored 0/300 on dev) | the GRPO questions (Q3, Q5a, Q5b) |
| Caveat | leaves no confirmatory test of robustness on real or re-phrased requests | introduces two comparisons that were not in the original family, chosen after M1's dev result (98% vs B0 59%) was known; dev is not test, but the choice is post-hoc with respect to dev, and the amendment must say so |

Why I lean to B: Q7 (real + rephrased requests vs the rule-based baseline) is the comparison the project's claim rests on; with variant A the only confirmatory result would be one with an enormous expected effect. B keeps one question about each of: untuned base, teacher-as-baseline (X1), rules baseline on real-world-like input. An optional fourth (Q5': M1 - B0 on test-compositional, m = 4) is possible; I did not include it because B0's compositional gaps are already large on dev (27% on 4-family tasks) and it adds little.

## Holm recomputed: detectable differences (80% power, two-sided, paired normal approximation; "disagree" = share of tasks on which the two systems differ, an assumption not a measurement), percentage points

| split | n | m=1 (alpha .05): disagree 15% / 30% | m=3 (alpha .0167): 15% / 30% | m=4 (alpha .0125): 15% / 30% |
|---|---|---|---|---|
| test-iid | 500 | 4.9 / 6.9 | 5.6 / 7.9 | 5.8 / 8.2 |
| test-iid dedup (descriptive) | 396 | 5.5 / 7.7 | 6.3 / 8.9 | 6.5 / 9.2 |
| test-compositional | 200 | 7.7 / 10.9 | 8.9 / 12.5 | 9.1 / 12.9 |
| test-phrasing | 200 | 7.7 / 10.9 | 8.9 / 12.5 | 9.1 / 12.9 |
| test-real + test-phrasing (real about 100) | 300 | 6.3 / 8.9 | 7.2 / 10.2 | 7.5 / 10.6 |

The 5-point minimum meaningful difference stays an interest threshold, not a promise of power: with m = 3, Q7' can detect about 7-10 points and Q4' about 6-8 points.

## What changes in the repo if you finalise (not done)

* `eval/PREREGISTRATION.md`: append the dated section above; mark lines 59 (systems list), 62 (family), 79-85 (SFT-to-GRPO, GRPO stopping rules, shuffled control, 50-output inspection) as inactive by reference to the amendment; the FINAL text is not edited in place.
* `training/config.py:170` `PREREG_COMPARISONS`: variant A = one tuple `("Q2 M1-B2", "B2", "M1", "test-iid")`; variant B = Q2, `("Q4' M1-X1", "X1", "M1", "test-iid")`, `("Q7' M1-B0 real+phrasing", "B0", "M1", "test-real+test-phrasing")`.
* `tests/eval/test_final_report.py:130` pins the family and must be updated in the same commit; `eval/final_report.py` must accept a run with no M3 results and print "M3 not trained; see D-040". `eval.stats.holm` needs no change (it already takes any number of p-values).
* Anything else that names M3 in `PHASES.md` and `EVALUATION.md` gets a one-line pointer to the amendment.

## Not decided here

* If you later do train M3, this amendment is void and the original family stands (nothing above changes the original text).
* Whether to hand-inspect 50 random passed M1 outputs (the old inspection step applied to M3 only). Suggested yes, as it is cheap.
