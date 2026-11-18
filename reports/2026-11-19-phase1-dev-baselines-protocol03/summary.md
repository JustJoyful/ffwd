# B0 on the final dev split, and the effect of the allowlist change (19 Nov 2026)

B0 is the frozen regex baseline, unpatched. Dev only; no test split touched. Wilson 95% intervals.

| run | overall | 1 family | 2 families | 3 families | 4 families | ambiguous | unsupported |
|---|---|---|---|---|---|---|---|
| final dev v1 (`B0-regex-dev-v1`) | 178/300 = 59% [54%, 65%] | 51/61 = 84% [72%, 91%] | 79/127 = 62% [54%, 70%] | 31/71 = 44% [33%, 55%] | 8/30 = 27% [14%, 44%] | 0/2 = 0% [0%, 66%] | 9/9 = 100% [70%, 100%] |

(Family columns exclude ambiguous/unsupported tasks, as in `2026-11-19-phase1-dev-baselines-pinned`.)

## 1. Effect of the allowlist change alone: 177 -> 177, no task flipped
`B0-regex-prev-dev-v1` is B0 on the PREVIOUS dev file (sha256 635c5bd9bb, the 300 tasks of the 177/300 run), now under protocol 0.3.0. Same tasks, same B0, same FFmpeg 5.1.1; only the validator differs. Result 177/300, identical per task. In 12 episodes of the final-dev run the validator now rejects `-display_rotation` (`option not allowed`) instead of FFmpeg failing on it: same outcome (B0 falls back to `unsupported`), earlier, with a cleaner message.

## 2. Final dev vs previous dev: 178 vs 177 is not a regrade
The dev split was re-drawn (F3 widening and the refreshed probes change which contents exist), so the 300 tasks differ. B0 passes 11 of the 34 final-dev tasks that contain lossless rotation (F5) because it still emits `-display_rotation`; that is the standing gap between B0 and the 5.1.x dialect, not something this rebuild changed. The bar for M1/M3 on final dev: 59% overall, 44% on 3-family tasks.

## Housekeeping
Job output of the `B0-regex-dev-v1` run went to `data/jobs/B0-regex-dev-v1`, the same directory name as the 16 Nov baseline's job dir (results of that run are untouched in `reports/2026-11-16-phase1-dev-baselines/`; some per-task job folders in the shared dir may have been overwritten). Use distinct `--out` basenames from now on.
