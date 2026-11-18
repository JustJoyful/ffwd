# B0 on the pinned FFmpeg (19 Nov 2026): what changed and why

Dev only; no test split touched. Wilson 95% intervals; failed/invalid episodes count as failures. B0 is the frozen regex baseline (`b0-frozen-paraphrase`); it was **not** patched. Per-run manifests (commit, FFmpeg version, tasks hash) are in each subdirectory.

| B0 run | overall | 1 family | 2 families | 3 families | 4 families | ambiguous | unsupported |
|---|---|---|---|---|---|---|---|
| old dev v1, FFmpeg 9.0.2 (16 Nov report) | 158/300 = 53% [47%, 58%] | 33/37 = 89% [75%, 96%] | 79/129 = 61% [53%, 69%] | 35/107 = 33% [25%, 42%] | 6/20 = 30% [15%, 52%] | 0/2 = 0% [0%, 66%] | 5/5 = 100% [57%, 100%] |
| old dev v1, pinned 5.1.1 | 151/300 = 50% [45%, 56%] | 32/37 = 86% [72%, 94%] | 76/129 = 59% [50%, 67%] | 32/107 = 30% [22%, 39%] | 6/20 = 30% [15%, 52%] | 0/2 = 0% [0%, 66%] | 5/5 = 100% [57%, 100%] |
| NEW dev v1, pinned 5.1.1 | 177/300 = 59% [53%, 64%] | 51/62 = 82% [71%, 90%] | 82/136 = 60% [52%, 68%] | 29/68 = 43% [32%, 54%] | 6/23 = 26% [13%, 46%] | 0/2 = 0% [0%, 66%] | 9/9 = 100% [70%, 100%] |

(Family columns exclude ambiguous/unsupported tasks; the 16 Nov report counted those inside "1 family", hence 33/37 here vs 38/44 there. Overall and the other columns are identical for the old run.)

## 1. Effect of the pin alone: old dev v1, 9.0.2 -> 5.1.1: 158 -> 151 (-7 tasks)
Same 300 tasks, same B0, only the FFmpeg build changed. Exactly 7 tasks flipped pass -> fail, none the other way:
- **6 lossless-rotation tasks** ("turn it 90 degrees to the left without re-encoding", "rotate 180 ... without losing quality", plus compositions containing F5): frozen B0 emits `-display_rotation`, which FFmpeg 5.1 does not have (`Unrecognized option 'display_rotation'`), so the run fails and B0 gives up with `unsupported`. This is the dialect gap D-024 predicted; the browser could not run those commands either.
- **1 size-cap task** (`dv-c6b9a24e15-sympt`, "under 1 MB"): B0's bitrate-targeted encode produced 1,001,188 bytes against the 1,000,000 cap (0.12% over) on 5.1.1's x264. On 9.0.2 it landed just under. That earlier pass was a knife-edge pass; it is an encoder-build difference, not a checker change.

## 2. New dev v1 (different tasks): B0 = 177/300 = 59% [53%, 64%]
The corpus and the task mix changed, so this is a **new baseline, not a regrade of the old number**: the bar for M1/M3 on dev v1 is now 59% overall and 43% on 3-family tasks (was 53% / 33%). The rise is not an improvement of B0: the mix differs (fewer 3-family tasks, 68 vs 107, and more single-family ones, 62 vs 37) and B0 happens to solve a larger share of the new 3-family tasks (29/68 = 43% vs 32/107 = 30%). I have not analysed which task properties drive that. B0 still fails lossless rotation on the pinned build (11/36 of the new-dev tasks that contain F5 pass), and still never asks (0/2 ambiguous) while refusing unsupported correctly (9/9).

## 3. B2 not re-run
B2 (stock Qwen3-0.6B) scored 0/300 on the OLD dev because it never emits a valid action (protocol failure, no FFmpeg involved). I expect it to stay at 0 on any task set (the failure happens before any FFmpeg call), but that is a prediction, not a measurement; I did not spend a re-run on it. the first model number that matters on the new dev is M1.
