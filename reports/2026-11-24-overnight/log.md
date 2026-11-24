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
- 03:49 IST (post.sh): test row finished (3 manifests); starting the queue
- 03:49 IST (post.sh): start: row analysis
- 03:49 IST (post.sh): ok: row analysis
- 03:49 IST (post.sh): start: ff main to integration
- 03:49 IST (post.sh): ok: ff main to integration
- 03:49 IST (post.sh): start: pnpm install
- 03:50 IST (post.sh): ok: pnpm install
- 03:50 IST (post.sh): start: pnpm build
- 03:50 IST (post.sh): ok: pnpm build
- 03:50 IST (post.sh): start: pnpm size
- 03:50 IST (post.sh): FAILED(1): pnpm size
- 03:50 IST (post.sh): skipped (an earlier app gate failed): build tests
- 03:50 IST (post.sh): skipped (an earlier app gate failed): e2e (scripted model, real ffmpeg.wasm)
- 03:50 IST (post.sh): start: real-model smoke of /app
- 03:50 IST: TEST ROW DONE 855/900 (95.0%) vs M3 Q8_0 867/900; pooled diff -1.33 pp [-2.67,-0.11]; GUARD NOT SHOWN (lower bound -2.67 vs -2.0); loss concentrated in test-phrasing (-3.5 pp). Analysis written (reports/2026-11-23-phase-1-browser-row/report). post.sh running the app chain (ff main done). MORNING_REPORT section 1 filled.
- 03:51 IST (post.sh): FAILED(1): real-model smoke of /app
- 03:51 IST (post.sh): start: iGPU parity (100 dev tasks)
- 03:56 IST: post.sh ran: analysis ok, ff main ok, build ok, size FAILED (home 117.45 ok; chore page 121.06 > 120, D asked to cut 1.06+ kB), build tests/e2e skipped by my gate, smoke ran (flow works end to end incl. real model plan; 2 script bugs, fixed on integration 92fbdd8). iGPU parity RUNNING on Intel gen-12lp (4 threads, 7 GB). post2.sh queued (waits for ALLDONE): ff main, build, size, build tests, e2e, smoke rerun. Push fixed (a 424 MB browser profile had been committed by mistake: removed, .gitignore rule added).
- 03:57 IST: merged stream-D 4081b24 (chore pages use plain <a> instead of react-router Link: removes a 3.45 kB chunk, expected chore page 121.06 -> about 117.6 kB; trade-off: full page loads between marketing pages) into integration WITHOUT running tests (iGPU job running); post2.sh will build, size and test it.
- 03:58 IST: DEVIATION from the plan, recorded: iGPU (Intel gen-12lp, 4 threads) runs at about 130-175 s per turn (4.3 tok/s generating, 10 tok/s prompt) against 2 s on the RTX: the 100-task parity would take 12+ hours and the verdict on the 5 s criterion is already clear. post.sh replaced by post3.sh: stops iGPU parity after 4 tasks (SUBSET), speedprobe f16 vs q8_0+FA on the iGPU, F4 coexistence, load times, CPU path stopped after 5 tasks (SUBSET), then ALLDONE so post2.sh (build/size/tests/e2e/smoke rerun) starts. Full 100-task runs can be done later if wanted.
- 04:37 IST: iGPU parity 2/4 capped tasks (about 20 min per task; Intel gen-12lp, 4 threads), post3.sh alive and will stop it at 4 (ETA about 05:15), then speedprobe f16 vs q8, coexist, load times, CPU path (5 tasks), then post2.sh (build/size/tests/e2e/smoke). RAM 4.5 GB free. D's chore fix already merged (untested). Nothing new started.
- 04:46 IST (post3.sh): igpu reached 4 tasks: stopping it (subset report)
- 04:48 IST (post3.sh): speedprobe iGPU kv=f16
- 04:48 IST (post3.sh): FAILED speedprobe kv=f16
- 04:48 IST (post3.sh): speedprobe iGPU kv=q8
- 04:48 IST (post3.sh): FAILED speedprobe kv=q8
- 04:48 IST (post3.sh): iGPU F4 coexistence
- 04:48 IST (post3.sh): FAILED coexist
- 04:48 IST (post3.sh): iGPU load times
- 04:48 IST (post3.sh): FAILED loadtimes
- 04:48 IST (post3.sh): CPU path under limits: start
- 04:50 IST (post3.sh): limits reached 5 tasks: stopping it (subset report)
- 04:52 IST (post3.sh): post3 done
- 04:52 IST (post2.sh): first queue finished; starting the second (app build, size, build tests, e2e, smoke rerun)
- 04:52 IST (post2.sh): start: ff main to integration
- 04:52 IST (post2.sh): ok: ff main to integration
- 04:52 IST (post2.sh): start: pnpm build
- 04:52 IST (post2.sh): ok: pnpm build
- 04:52 IST (post2.sh): start: pnpm size
- 04:52 IST (post2.sh): ok: pnpm size
- 04:52 IST (post2.sh): start: build tests
- 04:52 IST (post2.sh): ok: build tests
- 04:52 IST (post2.sh): start: e2e (scripted model, real ffmpeg.wasm)
- 04:53 IST (post2.sh): ok: e2e (scripted model, real ffmpeg.wasm)
- 04:53 IST (post2.sh): start: real-model smoke of /app (rerun)
- 04:53 IST (post2.sh): ok: real-model smoke of /app (rerun)
- 04:53 IST (post2.sh): post2 ALLDONE2
- 05:19 IST (post4.sh): start: speedprobe iGPU kv f16
- 05:21 IST: queues finished earlier than planned. SECOND QUEUE ALL GREEN: size home 117.44 / chore 117.53 kB (limit 120), build tests 31 pass, e2e 32 pass 7 skipped (trim, 9:16, audio chores incl.), smoke rerun passed all 8 steps. iGPU subset: 4 genuine tasks, 0 pass, output GARBAGE on Intel gen-12lp, median 133 s/turn; CPU 4 threads: 12/12 pass, median 3.2 s. The 96/88 error rows are artifacts of stopping the runs (excluded, subset_summary.json). iGPU speedprobes/loadtimes/coexist failed on a port clash (my sequencing bug) and are being rerun. MORNING_REPORT sections 2 and 3 filled.
- 05:21 IST (post4b.sh): start: speedprobe iGPU kv f16 with text
- 05:22 IST: ROOT CAUSE of the iGPU failure: q8_0 KV + flash attention (f16 KV: 27 tok/s, warm turns 2.4 s on the Intel iGPU). post4b.sh running: text sanity probe with f16, then (if sane) full 100-task iGPU parity with f16 KV, load times, coexistence. Morning report updated; decision for owner: f16 KV default vs q8_0 + canary.
- 05:24 IST (post4b.sh): ok: speedprobe iGPU kv f16 with text
- 05:24 IST (post4b.sh): f16 output sane: no
- 05:24 IST (post4b.sh): post4b done
- 05:58 IST (post4c.sh): start: A f16 repeat (text)
- 05:58 IST: RETRACTION: the f16 probe with text capture is garbage and slow too (4.8 tok/s), unlike the earlier f16 probe (27 tok/s, no text): the iGPU cause is NOT established; MORNING_REPORT corrected. post4c.sh running three controlled probes (f16 repeat, f16 with Mesa shader cache disabled, q8_0+FA with cache disabled), about 10 min.
- 06:01 IST (post4c.sh): ok: A f16 repeat (text)
- 06:01 IST (post4c.sh): start: B f16, Mesa shader cache disabled
- 06:03 IST (post4c.sh): ok: B f16, Mesa shader cache disabled
- 06:03 IST (post4c.sh): start: C q8_0+FA, Mesa shader cache disabled
- 06:04 IST (post4c.sh): ok: C q8_0+FA, Mesa shader cache disabled
- 06:04 IST (post4c.sh): post4c done
- 06:12 IST: iGPU FINAL: output wrong in all 5 configurations tried (Q5 q8KV+FA, Q5 f16KV x2, Q5 f16 no mesa cache, Q8_0 f16KV); not KV, not quant, not shader cache; criteria: parity FAIL, tab responsive PASS (F4 21.0 s alone and together, stall 3.3 ms), load cold 2.4 s warm 1.6 s. MORNING_REPORT section 2 final. All queues idle.
- 06:54 IST: FINAL. Nothing running, RAM 6.7 GB free. ffwd-web main fast-forwarded to integration. MORNING_REPORT finalized (summary, decisions, launch checklist, what did not run). TEST_RUNS.jsonl ledger (3 lock rows) committed. No further check-ins scheduled.
