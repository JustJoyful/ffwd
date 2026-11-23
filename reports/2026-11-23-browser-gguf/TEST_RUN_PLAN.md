# Plan: ONE test-split run of "M3 Q5_K_M, wllama in the browser" as an extra row (23 Nov 2026). NOT STARTED.

Nothing here has been run on a test split. Nothing starts without the owner's approval of this plan and of the Amendment 4 text below. The 15 existing ledger rows and every Phase 1 number stay as they are; this adds rows, it never replaces M3 Q8_0.

## What is run

- **System id** `M3-browser`; **checkpoint string** (the lock key, frozen): `grpo-m3-ckpt60-q5_k_m+wllama-4.0.0+chromium-159.0.8154.6+webgpu+kv-q8_0+n_ctx8192`. (One string per frozen configuration: any change of quant, runtime version, browser build, flags or KV type is a different system and needs its own lock.)
- **Model** M3 = GRPO checkpoint-60, GGUF Q5_K_M, sha256 `bbf439b749c02c04b5227ab93fb1430263a7c567c15552b6e12ae3836cde1e11` (444,411,456 bytes). The KV choice (q8_0 K and V, flash attention on) and Q5_K_M itself are **the owner's to confirm before the freeze**; I recommend both (REPORT sections 5 and 7).
- **Runtime** wllama 4.0.0 (llama.cpp b12637), Chromium 159.0.8154.6, WebGPU path with the flags of `manifest.json`, `n_ctx` 8192, greedy, 512 new tokens, prompt `system-v1.txt`, `require_spec`, `stop_after_ask`, the prompt rendered by the JS chat-template port (ffwd-web commit pinned in the manifest), same harness, checker, run budget and ffmpeg 5.1.1 as every Phase 1 row. A prompt that would not fit in `n_ctx` ends the episode as not done (counted as a failure, not truncated).
- **Splits** all three, once each, in the Phase 1 order: test-iid, test-phrasing, test-compositional (900 tasks, the same tasks M3 Q8_0 saw, so the comparison is paired). test-real stays out (Phase 4 addendum).
- **Cost** $0 (no paid call). **Time** about 7 s per task from the dev run, so about 1 h 45 min of runtime plus start-up, in one sitting with the laptop on mains power and idle (no other GPU or heavy CPU job: latency is a reported output).

## Before it may start (all must be true)
1. Owner approves this plan and the frozen configuration.
2. **Amendment 4** is added to `eval/PREREGISTRATION.md` as a new, dated, post-hoc section (the file allows changes after the first test run only that way) and committed **before** the run. It says: the browser row is an extra, **descriptive** row outside the Amendment 3 fixed sequence and outside the family-wise error budget; it cannot change any Phase 1 result or conclusion; the analysis below is fixed in advance; infrastructure failures count as failures with the denominators kept.
3. A driver `eval/browser_test_run.py` exists, reviewed, with tests: it is `eval/browser_parity.py` (bridge, `BrowserPolicy`) plus the Phase 1 mechanics of `eval/phase1_run.py` (`acquire_test_run` BEFORE each split, skip a split that has a manifest, refuse a partial run, `STOP` file, one split per bridge process). Its dry run is the dev parity run already done (96/100 and 97/100 at this configuration, >= 95 required): re-run once on dev with the final driver and the frozen versions, and it must still be >= 95/100.
4. The versions, hashes and flags are written to the run manifest and match the frozen string; `git status` clean in both repos.

## Analysis fixed in advance (written into Amendment 4)
- **Primary (descriptive):** paired success difference M3-browser minus M3 Q8_0 on the 900 pooled tasks, bootstrap 95% CI, seed 20261115, the code path of `eval/stats.py` used for M3 vs M1.
- **Guard:** the same rule as M3 against M1: one-sided 97.5% lower bound of the pooled paired difference above -2.0 pp. Reported as "shown" or "not shown", with the interval; a missed guard is reported, not explained away.
- **Secondary, descriptive:** per split; M3-browser vs M1 and vs X1 as context only; needless-re-encode rate on the copy-eligible tasks (Q3a-style); invalid-action episodes; material spec error rate; episodes ended by the context rule (expected to be about 1%); latency from the bridge log (median, p90, max turn; prompt and generation tok/s).
- **Failure handling:** a bridge or browser crash mid-split leaves a partial run whose lock is spent; re-running needs a written supersede reason from the owner. There is no silent retry.

## Report
An addendum folder `reports/<date>-phase-1-browser-row/` with `summary.md`, `results.json`, `manifest.json` and the three run directories, plus one added line in the Phase 1 report index pointing to it. `reports/2026-11-23-phase-1/summary.md` is not edited. The row is labelled "M3 Q5_K_M (wllama, browser), extra row" wherever it appears; M3 Q8_0 stays the headline model.

## Risks
- One machine, one browser build: the result describes this configuration on an RTX 3050 laptop, not the field. State it.
- n = 900 narrows the paired interval. My estimate (not computed on test data): if the two systems disagree on about 3% of tasks, as on the dev sample, the half-width is roughly 1 to 1.5 pp, which can show "no loss larger than 2 pp" only if the true gap is small; a wider interval is an honest outcome, not a failed run.
- The runtime build differs from the native one (b12637 against b12032), so the row measures the whole browser stack, not only the quantisation.
- Needs the 4.0.0 wllama release, which is days old; a bug fix release between now and the run changes the checkpoint string and needs a fresh dev check.
