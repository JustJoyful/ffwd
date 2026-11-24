# Validator bypass audit

Old validator: `git show ca3467f~1:training/env/validator.py`; new: working tree. Script: `eval/audit_validator_bypass.py`.

Total: 37305 episodes, 53705 run actions (10259 unique arg lists), 0 with a backslash inside single quotes, **0 affected** (old accepted, new rejects).

| dataset | files | episodes | run actions | backslash in quotes | affected |
|---|---|---|---|---|---|
| data/models/grpo-control-hub | 5 | 9 | 9 | 0 | 0 |
| data/models/grpo-m3-ckpt50-hub | 4 | 6 | 6 | 0 | 0 |
| data/models/grpo-m3-ckpt60-hub | 3 | 3 | 3 | 0 | 0 |
| data/sft/m1-v1 | 3 | 5775 | 6202 | 0 | 0 |
| data/tasks-hard/dev-recovery | 3 | 500 | 500 | 0 | 0 |
| data/tasks-hard/overnight | 1 | 1813 | 1813 | 0 | 0 |
| data/tasks-hard/recovery-base | 2 | 420 | 420 | 0 | 0 |
| data/tasks-hard/recovery-pilot | 3 | 600 | 600 | 0 | 0 |
| data/tasks-hard/widened-pilot | 2 | 300 | 300 | 0 | 0 |
| data/tasks/dev | 4 | 415 | 415 | 0 | 0 |
| data/tasks/test-compositional | 1 | 200 | 200 | 0 | 0 |
| data/tasks/test-iid | 1 | 458 | 458 | 0 | 0 |
| data/tasks/test-phrasing | 1 | 176 | 176 | 0 | 0 |
| data/tasks/train | 2 | 4265 | 4265 | 0 | 0 |
| data/teacher/bulk-20261119 | 9 | 9762 | 21252 | 0 | 0 |
| data/teacher/smoke | 4 | 1960 | 4322 | 0 | 0 |
| data/teacher/teacher-pilot-20261119 | 3 | 37 | 84 | 0 | 0 |
| reports/2026-11-15-phase-0 | 29 | 133 | 145 | 0 | 0 |
| reports/2026-11-16-paraphrase-robustness | 7 | 77 | 91 | 0 | 0 |
| reports/2026-11-16-phase0-followups | 21 | 241 | 276 | 0 | 0 |
| reports/2026-11-16-phase1-dev-baselines | 6 | 286 | 286 | 0 | 0 |
| reports/2026-11-19-m1-export-smoke | 4 | 1 | 5 | 0 | 0 |
| reports/2026-11-19-phase1-dev-baselines-pinned | 6 | 563 | 563 | 0 | 0 |
| reports/2026-11-19-phase1-dev-baselines-protocol03 | 6 | 556 | 556 | 0 | 0 |
| reports/2026-11-19-teacher-pilot | 3 | 37 | 84 | 0 | 0 |
| reports/2026-11-19-x1-dev | 6 | 57 | 65 | 0 | 0 |
| reports/2026-11-20-g3-pilots | 21 | 1453 | 1758 | 0 | 0 |
| reports/2026-11-20-m1-dev | 4 | 289 | 328 | 0 | 0 |
| reports/2026-11-20-m1-parity | 5 | 98 | 106 | 0 | 0 |
| reports/2026-11-20-reward-variance | 9 | 262 | 262 | 0 | 0 |
| reports/2026-11-20-t18-pass-rates | 9 | 69 | 69 | 0 | 0 |
| reports/2026-11-21-control-dev | 5 | 289 | 325 | 0 | 0 |
| reports/2026-11-22-m3-ckpt50-dev | 3 | 289 | 332 | 0 | 0 |
| reports/2026-11-22-m3-ckpt60-dev | 3 | 289 | 332 | 0 | 0 |
| reports/2026-11-22-m3-q4km-parity | 5 | 195 | 321 | 0 | 0 |
| reports/2026-11-22-phase1-dryrun-runs | 15 | 36 | 36 | 0 | 0 |
| reports/2026-11-22-phase1-runs | 45 | 3292 | 3623 | 0 | 0 |
| reports/2026-11-23-browser-gguf | 45 | 489 | 667 | 0 | 0 |
| reports/2026-11-23-igpu-sim | 21 | 12 | 12 | 0 | 0 |
| reports/2026-11-23-m3-q5km-parity | 5 | 196 | 210 | 0 | 0 |
| reports/2026-11-23-m3-q6k-parity | 5 | 196 | 204 | 0 | 0 |
| reports/2026-11-23-mlc-parity | 24 | 269 | 937 | 0 | 0 |
| reports/2026-11-23-phase-1-browser-row | 26 | 932 | 1087 | 0 | 0 |

Affected: none
