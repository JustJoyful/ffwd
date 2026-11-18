# Teacher pilot (19 Nov 2026), G1

DeepSeek V4 Flash, frozen prompt v1 (sha256 56e7d721...), thinking off, spec-first loop, **20 train tasks** chosen by `training.teacher.run.pilot_selection` (every family F1-F12 incl. F11, 1 ambiguous, 1 unsupported, 6 compositions), run off-peak (23:12 UTC) through `BudgetGuard`, cap $0.05.

| measure | result | gate |
|---|---|---|
| kept-rate | **19/20 = 95%** | >= max(40%, X1_dev - 15 pp) = **82%** (X1 dev 58/60 = 97%) -> pass |
| cache-hit ratio | **83.9%** | >= 60% -> pass |
| cost | **$0.0125** ($0.00063/task) | <= $0.05 -> pass |
| 10 hand-read trajectories show no format/checker problems | **NOT satisfied** (see below) | owner condition |

Kept by family: every single-family task 1/1 except F6 1/2; both F12+F1+F5, F3+F1 and F3+F4+F1+F12 compositions kept (2/2 each); unsupported 1/1; F11 1/1 (the filter-offset false negative did not bite: the teacher used `-itsoffset`). The one failure is the ambiguous task "make it smlaler": the teacher guessed a 3 MB spec and ran twice before asking; the protocol wants the question first, so rejecting it is right.

## Hand-read (10 kept + the 1 failure; `handread.md` has my notes)
What is good: specs and commands are sound; the checker confirms every pass; recoveries are real (F5: applied `rotate=270` for "left", the checker said actual 90, fixed to `rotate=90`; F11: first put `-itsoffset` before the wrong `-i`, measured +78.7 ms, moved it). The new prompt line works: lossless rotation is expressed with `-metadata:s:v:0 rotate=`, never `-display_rotation`.

Problems found:
1. **Invalid-action turns inside kept trajectories: 5 of 19 kept (5 invalid turns).** The teacher copies the probe's container string (`mov,mp4,m4a,3gp,3g2,mj2`) into `spec.container`, or writes `height: -2`, gets `invalid action`, and retries. The SFT loss is on every assistant turn, so the student would learn to emit schema-invalid specs. **Mitigation written (not a paid step):** `training/sft/dataset.py::drop_invalid_turns` removes the invalid assistant turn and its error message when building examples (counted in `stats.json`); failed *checker* attempts are kept as recoveries.
2. **Wrong `nearest_supported` on an unsupported task, and the scorer does not notice.** "blur everyone's face" has gold `nearest_supported: null`; the teacher answered `"F4"`. `score()` only checks the unsupported flag, so the label would be trained on. Options (owner's call, it changes scoring/data): (a) keep only unsupported trajectories whose `nearest_supported` equals the gold, (b) overwrite it with the gold at build time, (c) leave it and accept noisy labels on ~5% of tasks.
3. Minor: the model-visible probe gives the container as ffprobe's raw `format_name`; that is the root of problem 1 and the student sees the same string. Not changed (frozen input format); SFT on cleaned data teaches `mp4`.

## Decision for the owner
Gates 1-3 numerically pass; the hand-read condition is not clean, so per your rule **I stopped before the bulk run** (nothing beyond the pilot was spent). My recommendation is to proceed to bulk with the mitigation in place and option (a) for unsupported, both applied at SFT build time (the raw trajectories stay unmodified): expected extra loss is small (~5% of kept trajectories are the unsupported kind; invalid turns are removed, not whole trajectories). Pricing page re-check is still due before bulk. Spend to date: $0.0573 + $0.0423 (X1 dev) + $0.0125 = **$0.112** of $4.
