# Phase 1 dry run on 10 dev tasks (22 Nov 2026, before the preregistration was marked FINAL)

Purpose (owner, A1 decision 5): rehearse the exact A2 path with the same scripts, flags, budget guard and report writer. **Dev tasks only (the first 10 of `data/tasks/dev/v1.jsonl`); no test split was read, no test lock was taken, nothing here is a result.** The one run directory per system is reused for all three pseudo-splits in the report, so the table columns repeat.

Commands (the real run uses the same two, without `--dry-run-dev --limit 10`):
`uv run python -m eval.phase1_run run --runs-root reports/2026-11-22-phase1-dryrun-runs --dry-run-dev --limit 10`
`uv run python -m eval.phase1_run report --runs-root reports/2026-11-22-phase1-dryrun-runs --dry-run-dev --out reports/2026-11-22-phase1-dryrun`

| system | tasks | passed | cost | wall time (10 tasks, incl. server start) |
|---|---|---|---|---|
| B0 | 10 | 5 | $0 | 8 s |
| B2 (stock Qwen3-0.6B, Q8_0) | 10 | 0 | $0 | about 4.2 min (25 s per task: it never emits a valid action and runs to the token limit) |
| M1 (Q8_0) | 10 | 10 | $0 | about 34 s |
| M3 (checkpoint-60, Q8_0) | 10 | 10 | $0 | about 27 s |
| X1 (DeepSeek V4 Flash) | 10 | 10 | $0.00587 (estimate printed first: $0.0070; cap $0.01; off-peak 11:21 UTC) | 52 s |

Result: all five systems ran to completion with no errored episode, the report writer produced `summary.md`, `results.json`, `by_family.csv` and `manifest.json` (hashes, versions, costs), the sequence stopped at Q3b with Q4 labelled descriptive, and the guard line printed. llama-server was started under `systemd-run --user --scope -p MemoryMax=4G` and stopped by pid; no server was left running.

Found and fixed during the rehearsal (both before FINAL):
1. `manifest.json` counted a run directory's cost once per pseudo-split (0.0176 instead of 0.0059); it now counts each directory once. The first copy of this report (untracked, never committed) was deleted and rebuilt.
2. A metric with no tasks (here: copy-eligible tasks are rare in 10) crashed the sequence; it now stops with "NOT computable (no tasks)". Test added.

The single-run lock path is not exercised by a dev run (dev has no lock), so it was rehearsed separately against a temporary ledger and a temporary FINAL marker with 3 dev tasks relabelled as `test-iid` and B0: without `--checkpoint` refused; with it, ran and recorded one ledger row; the same (system, checkpoint, split) again refused (`TestAlreadyRun`). The real `reports/TEST_RUNS.jsonl` does not exist.

Timing for the real run (900 tasks per local system, from the above): B2 about 6 h (the slow one), M1 and M3 about 30 min each, B0 seconds, X1 about 5 s per task (about 43 min for test-iid, about 78 min for all three splits).

Things the rehearsal does not cover: the dedup column (needs test-iid), the lock check inside `final_report` against the real ledger (unit-tested), and X1 on the full cap.
