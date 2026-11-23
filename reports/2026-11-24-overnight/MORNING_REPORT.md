# Morning report (24 Nov 2026). Filled in as results land; anything marked PENDING had not finished when this was last saved.

Timeline and check-ins: `log.md` in this folder. Hard limits kept all night: nothing public, no money spent, no preregistration/checker/metric change, one heavy browser job at a time under the memory cap.

## 1. Browser test row (M3 Q5_K_M, wllama, WebGPU): PENDING
- Frozen configuration (Amendment 4): `grpo-m3-ckpt60-q5_k_m[sha256:bbf439b7]+wllama-4.0.0[libllama-b12637-0b51bb2]+chromium-159.0.8154.6+webgpu+kv-q8_0-fa+n_ctx8192`. Amendment 4 was pushed to the private remote at 23:56 IST on 23 Nov; the first lock was taken at 01:46 IST on 24 Nov.
- Dev dry run through the final driver: **97/100** (needs >= 95): passed, no infrastructure errors.
- Results table and analysis: `reports/2026-11-23-phase-1-browser-row/report/summary.md` (PENDING until the three splits finish).
- Honest notes for this row: it measures the Python harness loop driving the browser model, not the app's own JS loop (the JS loop ends a job on the first passing run, the Python one waits for `finish`); a circuit breaker watched the run; the row shared the machine with a ~35 s niced unit-test burst at 01:47 IST (native-ffmpeg conformance) and light niced unit tests by subagents; one laptop, one browser build, one seed; the row is descriptive and M3 Q8_0 stays the headline.

## 2. iGPU simulation and CPU path under budget limits: PENDING
Simulation (labelled "Intel UHD, simulated budget limits"; a real budget-laptop run stays on the launch checklist): only the Intel Vulkan driver visible, adapter asserted Intel, 4 physical cores, 7 GB hard cap. Pass criteria: >= 95/100 parity, <= 5 s median turn, responsive tab. Results in `reports/2026-11-23-igpu-sim/` (parity, F4 coexistence, load times, then the CPU path under the same limits). Note: with only the Intel driver visible every power preference picks Intel, so the "low-power vs default" answer comes from the dual-GPU `env.json` files (`byPreference`) of the dry run and the test row.

## 3. The app (branch `integration`, merged from four parallel streams; on `main` only after the post-row window)
Starting point: `reports/2026-11-23-site-inventory/INVENTORY.md`. 597 unit tests green and lint clean on `integration`.
- Model runtime (stream A): `app/model/*` (streaming SHA-256, model host and worker, client with consent/progress/retry, store wiring, capability path).
- Agent engine (stream B): model errors end a job as failed with the "too long" / "model unavailable" sentences (never success); loop invariants pinned with 77 tests; conformance suites wired in Node (validator 39, describe-spec 8, offset 8, frames 9, invariants 13, quality 6, rotation 7 of 12; the other 5 need ffmpeg 5.x and run in CI); a privacy leak fixed (ffmpeg log tails sent to the model carried the user's file name).
- Tool UI (stream C): model loader (consent, progress, start, failure, declined), path notice, request gating while the model is not ready, "Picture: removed" chips for audio results, e2e specs for 9:16 vertical and extract audio.
- Pages and infra (stream D): model-load analytics (disabled by default), real-path `capability_checked`, `_headers` with verified hosting facts only, an e2e CI job, a wider test-real guard, a lazy-load home bundle change (expected about 114 to 115 kB against the 120 kB budget; the limit was not raised).
- Verified in a browser: PENDING (post-row window: build, size, build tests, e2e on trim / 9:16 / extract audio with the scripted model, then the real-model smoke with a screenshot per step in `reports/2026-11-24-overnight/app-smoke/`).
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
