# Overnight log (24 Nov 2026). Resume from here after any usage limit or restart.

Times are IST. One line per check-in; newest at the bottom. Hard limits: nothing public, no money, no prereg/checker/metric changes, ONE heavy browser job at a time under the memory cap, abort if available RAM < 2 GB, stop a stream on a failed gate and write it up.

## State to resume from (written 01:55 IST)
- **Heavy-job queue (sequential, already running in the background):**
  1. Browser test row: `python -m eval.browser_test_run --runs-root reports/2026-11-23-phase-1-browser-row` (pid in `/tmp/claude-1000/testrow.pid`, log `/tmp/claude-1000/testrow.log`, per-split results in `reports/2026-11-23-phase-1-browser-row/runs/M3-browser-<split>/`). Locks are taken for each split before it runs; a crash leaves a partial split whose lock is spent (a rerun needs the owner's written supersede reason: do NOT rerun, write it up).
  2. `post.sh` (pid in `/tmp/claude-1000/post.pid`, log `/tmp/claude-1000/post.log`, script in the session scratchpad `.../scratchpad/post.sh`) starts by itself when the test row exits: row analysis -> fast-forward ffwd-web main to `integration` -> pnpm install/build/size/build tests/e2e -> iGPU simulation (Intel-only ICD, 4 cores, 7 GB) parity, coexist, loadtimes -> CPU path under the same limits. It prints `ALLDONE` at the end. If it died, read its log and run only the remaining steps by hand, one at a time.
- **App streams:** A (model runtime), B (agent/conformance), C (tool UI), D (pages/infra) are all merged on branch `integration` of `/home/joydeep/Projects/ffwd-web-int` (597 unit tests, lint clean). `main` of `/home/joydeep/Projects/ffwd-web` is still 0c61afe and is fast-forwarded by `post.sh` after the test row (the test row serves the spike files from main: do not edit main before then).
- **Not done yet:** real-model smoke of `/app` with screenshots (needs `VITE_MODEL_URL` pointing at a localhost server for the GGUF; one heavy job at a time); fresh-context review of the whole site branch; bundle measurement (post.sh runs `pnpm size`; stream D expects about 114 to 115 kB against the 120 kB budget; the limit must not be raised); e2e on 3 chores (post.sh runs `pnpm e2e`).
- **Light work for waiting periods:** morning report and launch checklist (`reports/2026-11-24-overnight/MORNING_REPORT.md`), review sheet for the 9 no-precedent components, model card fill-in, unit tests for untested branches, flow state diagram, plain-language copy for chore/privacy/requirements pages.
- **Note for the test-row report:** a niced unit-test run of about 35 s (including native-ffmpeg conformance) ran 01:47 to 01:48 IST during the first minutes of test-iid; later unit runs excluded it. Subagents also ran niced vitest runs during the row.

## Check-ins
- 01:55 IST: test-iid at 68/500; post.sh waiting on the row; log created.
- 02:04 IST: test-iid at 138/500; watchdog running (rowwatch.pid), post.sh rewritten (name-suffix fix, gates, per-step RAM watch, smoke before iGPU); wasm ?url fix + app-smoke committed on integration; morning report skeleton + component review written.
- 02:05 IST: test-iid at 148/500; model card filled (quant curve, browser, Q5_K_M shipping format, MLC finding, hashes); owner items listed with suggestions.
- 02:06 IST: test-iid at 151/500; APP_FLOW.md written. Remaining light items skipped on purpose to save usage: copy rewrites (pages already carry owner-review copy) and new unit tests (no vitest while the row runs).
- 02:36 IST: test-iid 387/500 (375 pass, 0 errors), watchdog alive, 4.3 GB free, no STOP flag; row ETA about 03:45; post.sh waiting. Light work done earlier; nothing new started (saving usage).
- 03:17 IST: test-iid DONE 483/500 pass, 0 errors; test-phrasing 171/200 (156 pass, 0 errors); compositional next; watchdog alive, no STOP flag, 3.9 GB free; ETA row end about 03:50; post.sh waiting.
