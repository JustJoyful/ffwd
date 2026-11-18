# Native FFmpeg 5.1.1 vs ffmpeg.wasm 5.1.4: parity over the checker conformance suite (19 Nov 2026)

**Result: 48/48 cases at parity** (this directory: `results.json`, `manifest.json`). Method (`eval/runtime_parity.py`, browser half `spikes/browser/e2e/parity-run.spec.ts`): every recipe in `packages/protocol/conformance/checker-{invariants,rotation,frames,quality,offset}.jsonl` runs (1) natively through the training executor on the pinned 5.1.1-static and (2) in ffmpeg.wasm core-mt 0.12.10 (FFmpeg 5.1.4, headless Chromium) through the browser's own argument rewriting; the single Python checker then judges BOTH outputs with the same spec. Parity = both runtimes succeed or fail together AND (passed, failed fields) are identical AND equal to the recorded expectation. Covers: implicit invariants, rotation (all four angles and the wrong-direction failure), frame-count boundary, quality floors, A/V offsets (itsoffset copies, filter delay limitation), loudness.

## What it found on the way (earlier runs kept as evidence)
- `...-run2/`: **47/48**. The two-input `concat` re-encode (F2 merge) **hung in ffmpeg.wasm** (native fine). `concat-thread-caps.json`: capping filter threads does not help. `concat-localisation.json`: two inputs without a filter, and audio-only concat, work; video concat hangs; concat A+V works when `-threads 1` is set **before each `-i`** (decoder threads), not only before the output (the harness's existing cap).
- Fix (harness only, the model never sees it): `capThreads` now also inserts `-threads 1` before every `-i` (`spikes/browser/src/harness-args.ts`, `FFMPEG_DECODE_THREADS`), unit-tested.
- `...-run3-fixed-harness/` still showed the hang: **a stale preview server** (left over from a killed run) served the pre-fix build. Not a result about the fix; `...-run4-fresh-build/` (this one) ran on the freshly built code. Nothing else changed between run3 and run4.
- A first aborted attempt left an empty `reports/2026-11-19-parity-native-5.1.1-vs-wasm-5.1.4/` (no results).

## What this does and does not show
- It shows the FFmpeg half of "what passes the checker runs in the browser" holds on 48 recipes, with 5.1.1 standing in for 5.1.4: **no patch-level difference was observable**. On that evidence a self-built 5.1.4 (proposal in `reports/PHASE1-STATUS.md`) is not needed for Phase 1; revisit for Phase 3 helper distribution.
- It does not test the TypeScript checker (Phase 2) or models; encoder output sizes/bitrates are not compared, only checker verdicts.
- The 150 s hard timeout means a browser hang is recorded as a case failure, not an infinite wait.
- Browser merges had never been exercised before this run (Phase 0 bench had no concat); F2 re-encode merges in the browser were broken until this fix.
- Re-run: `systemd-run --user --scope -p MemoryHigh=3500M -p MemoryMax=5G uv run python -m eval.runtime_parity --out reports/<date>-parity` (starts Chromium; kill any old `pnpm preview` on :4173 first).
