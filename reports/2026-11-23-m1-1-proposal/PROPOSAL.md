# M1.1 proposal: fix the two systematic spec bugs (23 Nov 2026). Proposal only, nothing started.

## 1. Where the wrong specs come from (measured on train data only)

Method: for every kept DeepSeek trajectory in `data/teacher/bulk-20261119/` I took the first `spec` action as the SFT builder sees it (after `drop_invalid_turns`) and graded it against the task's gold spec with `eval.spec_errors.material_errors`. Rotate = reference command contains transpose/rotate; speed = setpts/atempo.

| slice of the SFT source data | n | wrong |
|---|---|---|
| teacher, rotate tasks: width/height | 348 | 134 = 38% (gold has w/h on all 348) |
| teacher, other tasks: width/height | 971 | 73 = 7.5% |
| teacher, speed tasks: `end_s` | 509 | 174 = 34% (145 of them too large, the source span) |
| teacher, other tasks: `end_s` | 648 | 22 = 3.4% |
| paraphrase copies (2,005 kept; 1,896 in the mix) | 216 rotate, 267 speed | 97 and 89 wrong (copies of the same teacher specs) |
| oracle (gold spec verbatim) | 75 rotate, 159 speed | 0 wrong |

Conclusions:
- **The taskgen gold spec is right** (`end_s` 1.333 for "first 2 s at 1.5x"; rotated w/h swapped). The oracle, which replays it, has 0 errors.
- **The error is in the teacher's spec text.** The frozen prompt says "state a new length after a speed change" but never says to swap w/h after a rotation; DeepSeek ignores the first about a third of the time and misses the second at the same rate.
- **M1 copies the teacher's error rates.** Elsewhere: teacher 7.5% / 3.4%, M1 dev 7% / 3%. On rotate, teacher 38% against M1 35%. On speed, teacher 34% against M1 51%: the student picks the wrong form more often than the teacher produced it (my reading; not tested). Affected examples in the mix: roughly 300 teacher + 185 paraphrase, about 8% of 6,032.
- **Why success stays at 97%:** `training/env/loop.py` grades every run against the GOLD spec; the emitted spec is only logged (RULES 4.4). Neither the teacher's keep filter (checker pass plus label) nor GRPO (`spec_acc` weight 0, D-043) ever looked at it. The wrong spec matters in the product, where the user-confirmed spec drives the runtime check.
- GRPO cannot fix this: when every sample shares the error there is no within-group variance, so there is no gradient even with the term on.

## 2. Options

Budget: ledger settled $3.278 of $4.00 (the $2.675 plus $0.599 for the X1 test run); **$0.72 remains**. Measured GPU: M1 SFT 4.82 h on a T4 (17,340 s, 754 steps; about 5 h wall); GRPO main run 10.51 GPU-h (60 steps, about 0.175 h/step) plus 1.1 h lost to an OOM; shuffled control about 6.4 GPU-h (30 x 0.213). Kaggle quota is about 30 GPU-h per week.

| | (a) deterministic relabel | (a-drop) drop wrong ones | (b) regenerate with DeepSeek | (c) more rotate/speed tasks | (d) reward / checker term |
|---|---|---|---|---|---|
| Change | patch the spec action in existing trajectories from gold | filter them out | re-run teacher, keep only spec-correct | extra train-only contents, oracle-labelled | spec term in reward or checker |
| Files | new `training/sft/relabel.py` + test; flag in `training/sft/build.py`; D-049 | one filter in `build.py` | `training/teacher/run.py` plus a spec filter | builder flag in `taskgen/build.py` | `telemetry.py`, `config.py` |
| Data | about 490 of 6,032 examples edited (more with other fields) | about 490 removed | about 800 episodes plus paraphrases | up to about 700 more (oracle cap headroom) | none |
| DeepSeek | $0 | $0 | about $0.85 for about 1,290 episodes (35% rejection) plus paraphrases; **over the $0.72 left** | $0 (oracle) | $0 |
| GPU-h | 4.8 (SFT) | 4.8 | 4.8 | 4.8 | 11 to 17 (GRPO re-run), and no gradient on shared errors |
| GRPO re-run | optional | optional | optional | optional | yes |
| Risk | low; see below | loses 8% of data, biased to contents the teacher got right | breaks the cap; a prompt fix changes the frozen prompt hash and invalidates Phase 1 comparability | does not fix labels alone | reintroduces the noise D-043 removed; changing the checker is forbidden |
| Verdict | **do** | fallback | no | optional add-on | no |

**Option (a) in detail.** Replace only `video.width`, `video.height` and `time.end_s` in a spec action when it differs from gold beyond the metric tolerance (2 px, gold `tolerance_s`). The teacher's style, run command and finish note stay as they are. Paraphrases patch the same way through `paraphrase_of`. A trajectory is consistent after the patch because its command already passed the gold check. The same function could cover the other material fields (container, lossless, codec): 544 supported teacher examples have some material error (709 minus 165 unsupported/ambiguous rows that have no spec). That is the same method for a wider class; the owner decides the scope. Risks: finish notes can still quote the old numbers (ungraded, text only); patching removes the teacher's spec variance, which is the goal. The patch uses train-task gold only, so no test data is involved.

## 3. Cost and what to retrain

Recommended path: (a), then retrain SFT from the base model with the same hyperparameters (2 epochs, 2 x 8), using the existing Kaggle path (D-037), GGUF export and HF parity. That costs **$0 and about 5 GPU-h** (one session, under 12 h), plus local export and parity.

GRPO is **not** re-run at first. M1 to M3 moved the spec error only from 26% to 22%, because GRPO leaves specs alone. If M1.1 holds success, re-running GRPO from M1.1 (about 11 GPU-h without the control, about 17 with it, plus OOM risk) becomes an owner decision, made after seeing M1.1, not before. A cheap intermediate is a short corrective SFT continuing from M1's adapter on the relabelled rotate/speed subset (my estimate is 1 to 1.5 GPU-h, not measured, with forgetting risk).

## 4. How success is measured

Phase 1 test splits have each been run once and cannot be reused. A new preregistration, FINAL before any run, on **fresh data**:
- A new split built with a new seed and enriched sampling, at least 120 rotate and 160 speed tasks, hash-pinned, leakage-checked against train and the old splits (`eval.leakage`). Only M1 and M1.1 run on it, with X1 and M3 left out to spare the budget.
- Primary: paired rate of the two bug indicators (M1.1 against M1), McNemar with a Wilson CI. Hypothesis: M1's 35% falls to 10% or less, and 51% to 10% or less. Roughly 30 discordant pairs are enough at those sizes.
- Guard: overall success not lower than M1 by more than 2 pp (the Phase 1 rule). Secondary: material spec error rate overall, with all denominators kept.
- Dev v1 (31 rotate, 65 speed tasks) is a free pre-check, but it is not confirmatory.

## 5. Recommendation

Do **(a)**: relabel the three fields (or all material fields; the owner decides), retrain SFT (about 5 GPU-h, $0), check on dev, then run one preregistered comparison on a fresh enriched split. Keep (a-drop) as the fallback. Add (c) only if dev still shows a coverage gap. Skip (b) (over budget) and (d) (no gradient, and metric changes forbidden). Decide on a GRPO re-run only after M1.1's numbers are in.

Measured with throwaway scripts on train data only; no test split, test report folder or paid call was used. The ledger sum counts one unsettled $0.0012 reservation as spent.
