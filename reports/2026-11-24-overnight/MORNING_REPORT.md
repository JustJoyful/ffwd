# Morning report (24 Nov 2026). Filled in as results land; anything marked PENDING had not finished when this was last saved.

Timeline and check-ins: `log.md` in this folder. Hard limits kept all night: nothing public, no money spent, no preregistration/checker/metric change, one heavy browser job at a time under the memory cap.

## 1. Browser test row (M3 Q5_K_M, wllama, WebGPU): DONE. The preregistered guard is NOT shown.
Frozen configuration (Amendment 4): `grpo-m3-ckpt60-q5_k_m[sha256:bbf439b7]+wllama-4.0.0[libllama-b12637-0b51bb2]+chromium-159.0.8154.6+webgpu+kv-q8_0-fa+n_ctx8192`. Amendment 4 was pushed to the private remote at 23:56 IST on 23 Nov; the first lock was taken at 01:46 IST on 24 Nov; the dev dry run through the final driver scored 97/100. One run per split, 900 tasks, no infrastructure errors, no episode ended by the context rule. Full output: `reports/2026-11-23-phase-1-browser-row/report/` (`summary.md`, `results.json`, `manifest.json`).

| System | test-iid | test-phrasing | test-compositional | pooled |
|---|---|---|---|---|
| **M3-browser (Q5_K_M, wllama)** | 483/500 = 96.6% | 181/200 = 90.5% | 191/200 = 95.5% | **855/900 = 95.0%** |
| M3 Q8_0 (the headline) | 485/500 = 97.0% | 188/200 = 94.0% | 194/200 = 97.0% | 867/900 = 96.3% |
| M1 | 485/500 | 187/200 | 194/200 | 866/900 |
| X1 (DeepSeek teacher) | 483/500 | 188/200 | 195/200 | 866/900 |

- **Primary (descriptive), paired difference browser minus M3 Q8_0, three splits pooled: -1.33 pp, 95% CI [-2.67, -0.11].** Per split: test-iid -0.40 [-2.00, +1.20]; test-phrasing **-3.50 [-7.00, -0.50]**; test-compositional -1.50 [-4.50, +1.50].
- **Guard (Amendment 3 item 5, reused): one-sided 97.5% lower bound -2.67 pp against -2.0 pp: NOT shown.** Reported as it is: the browser configuration is not shown to be within 2 pp of M3 Q8_0 on the held-out splits, and the interval says it is measurably a little lower. The loss is concentrated in test-phrasing (7 fewer tasks than Q8_0 of 200).
- Context only: versus M1 -1.22 pp [-2.56, 0.00]; versus X1 -1.22 pp [-3.11, +0.56] (n = 900). Needless re-encode or fail on the 90 copy-eligible tasks: browser 5.6% against 4.4% for Q8_0 (+1.11 pp [-4.44, +6.67]). Material spec error rate about the same as M3 (22%, 23%, 13% by split). Invalid-action episodes: browser 2, Q8_0 5, M1 3.
- Latency (nothing else heavy ran; one 35 s niced unit-test burst at 01:47 IST and light niced subagent tests did): median turn 2.13 / 2.19 / 2.36 s by split, p90 3.5 to 4.1 s, max 20 to 22 s (long retry episodes); about 190 prompt tok/s and 53 generation tok/s.
- **What this does and does not say.** The 100-task dev parity (96 to 97 against 97) could not see a 1 to 2 pp gap; 900 tasks can. This row measures the whole browser stack (Q5_K_M weights, a different llama.cpp build, KV q8_0 cache, WebGPU kernels), not the quantisation alone, so it does not say which part costs the points. It changes no Phase 1 result or conclusion; M3 Q8_0 stays the headline. It also measures the Python harness loop driving the browser model, not the app's own JS loop (the JS loop ends a job on the first passing run; the Python one waits for `finish`).
- **Your decision (not mine).** Accept about 1.3 pp of success for a 444 MB download (against 639 MB for Q8_0), or look for a cheaper loss: candidates measured only on dev so far are Q6_K in the browser (98/100 on the dev sample, but 495 MB + 10.8 MB runtime = 505.9 MB, 6 MB over the approximate 500 MB limit) and an f16 KV cache (96 against 97 on dev: no evidence either way). Any new test-split run is a new system with its own lock and needs your approval; nothing was rerun.

## 2. iGPU simulation and CPU path under budget limits: PENDING
Simulation (labelled "Intel UHD, simulated budget limits"; a real budget-laptop run stays on the launch checklist): only the Intel Vulkan driver visible, adapter asserted Intel, 4 physical cores, 7 GB hard cap. Pass criteria: >= 95/100 parity, <= 5 s median turn, responsive tab. Results in `reports/2026-11-23-igpu-sim/` (parity, F4 coexistence, load times, then the CPU path under the same limits). Note: with only the Intel driver visible every power preference picks Intel, so the "low-power vs default" answer comes from the dual-GPU `env.json` files (`byPreference`) of the dry run and the test row.

## 3. The app (branch `integration`, merged from four parallel streams; on `main` only after the post-row window)
Starting point: `reports/2026-11-23-site-inventory/INVENTORY.md`. 597 unit tests green and lint clean on `integration`.
- Model runtime (stream A): `app/model/*` (streaming SHA-256, model host and worker, client with consent/progress/retry, store wiring, capability path).
- Agent engine (stream B): model errors end a job as failed with the "too long" / "model unavailable" sentences (never success); loop invariants pinned with 77 tests; conformance suites wired in Node (validator 39, describe-spec 8, offset 8, frames 9, invariants 13, quality 6, rotation 7 of 12; the other 5 need ffmpeg 5.x and run in CI); a privacy leak fixed (ffmpeg log tails sent to the model carried the user's file name).
- Tool UI (stream C): model loader (consent, progress, start, failure, declined), path notice, request gating while the model is not ready, "Picture: removed" chips for audio results, e2e specs for 9:16 vertical and extract audio.
- Pages and infra (stream D): model-load analytics (disabled by default), real-path `capability_checked`, `_headers` with verified hosting facts only, an e2e CI job, a wider test-real guard, a lazy-load home bundle change (expected about 114 to 115 kB against the 120 kB budget; the limit was not raised).
- **Verified in a real browser (first real-model smoke, 03:50 IST, WebGPU, model from localhost, screenshots in `reports/2026-11-24-overnight/app-smoke/`):** the whole flow worked: /app opened cross-origin isolated with WebGPU; a video was chosen; the model asked before downloading, downloaded (444 MB from localhost in seconds), was checked and started; the **real model made a correct plan** for "Cut the first 2 seconds off" (Keep 0:02 to 0:06, length 0:04, MP4, AAC) in 7 s; the job ran and every check passed; no console errors, no failed requests. Two steps were marked failed by the smoke SCRIPT, not the app (it read a progress bar that had already finished, and Playwright cannot drive the native save dialog); both are fixed in the script and the smoke is re-run in the second queue (`app-smoke-2/`).
- **Bundle (real build, `pnpm size`):** home page 117.45 kB gzip (was 123.49; limit 120, passes); a chore page 121.06 kB (over by 1.06 kB): stream D is finding the cut, the limit is not raised. Fonts 54.23 kB of 90.
- **Still PENDING (second queue, runs after the iGPU/CPU runs):** build tests, Playwright e2e on the three chores with the scripted model, smoke re-run, size re-check.
- Known gaps: no rules-only fast path in the app yet; the model host (HF or R2) does not exist, so a production build has no model URL (the loader says the model is not published yet); the desktop helper is not built; `shader-f16` requirement unknown; wllama's worker inside a module worker was unverified before the smoke (one likely bug already fixed: the wasm is now imported with `?url`).

## 4. Components built without a design precedent (for your review)
See `COMPONENT_REVIEW.md` in this folder (what each does and the simplest on-design option). The flow and both state machines are drawn in `APP_FLOW.md`.

## 5. LAUNCH CHECKLIST (for you)
1. **Model card and data card** (`docs/hf-cards/` in the model repo): 16 TODO(owner) items; suggested text in `MODEL_CARD_OWNER_ITEMS.md` here. Weights licence, seeds, repo ids, the DeepSeek review outcome, whether teacher trajectories may be uploaded.
2. **DeepSeek terms review**: nothing goes public before it. Then decide HF visibility.
3. **HF repo contents check** before flipping public: the GGUF Q5_K_M with sha256 `bbf439b7...` (444,411,456 bytes), no test-real clips, no teacher trajectories unless cleared, model card text approved, licence lines for every third-party asset. Flip public only after 1 and 2.
4. **Model host**: public HF repo primary, R2 fallback (R2 untested). Pin the revision hash in the app config; no URL exists yet.
5. **Cloudflare**: login, a Pages project, an R2 bucket and `assets.` host for the 31 MB ffmpeg core (over Pages' 25 MiB per-file cap), CORS/CORP headers, preview deploy, then production deploy. `SITE_URL` is still a placeholder and `pnpm check:release` refuses to ship with it.
6. **Analytics**: still off. Decide persistence and Do Not Track handling (currently respected), then set the key. PostHog under COEP credentialless is unverified.
7. **Copy to approve**: home, chore pages (5), privacy, requirements (now says the processor path works, with measured waits).
8. **Real devices**: run the bench kit on a friend's iGPU laptop (`node bench.mjs --model <gguf>` from the kit built by `node scripts/make-bench-kit.mjs`). The simulated iGPU here is not a budget laptop.
9. **Decisions still open**: `PROTOCOL_SOURCE_REPO` repo variable; memory floor (PRD 8 GB vs code 4 GB); the ESLint boundary rule (a hook blocks the config edit; a unit test enforces it); M1.1 scope; the "14 real clips" wording in the M1 hub README; stale text in `WEB_ARCHITECTURE.md` and `DESIGN.md` (local, gitignored).
10. **What I did not do**: nothing public; no deploy; no money; no HF change; no preregistration, checker or metric change.
