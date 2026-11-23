# PHASES: ffwd build plan

## Status

| Phase | Name | Status |
|---|---|---|
| 0 | Go/no-go spike | ✅ **GO** (16 Nov 2026; owner items open, see reports/2026-11-15-phase-0/summary.md) |
| 1 | Core model | ✅ **Test run done (22–23 Nov 2026)**: B0, B2, M1, M3, X1 on the three generated test splits; M3 (GRPO checkpoint-60, Q8_0) 867/900, M1 866/900. Preregistered Q2, Q7 and Q3a rejected, Q3b not, so Q4 is descriptive and the efficiency claim rests on Q3a and the guard. Report: `reports/2026-11-23-phase-1/` (read `LIMITATIONS.md`). **Still open: the owner's review of 50 passed outputs (`reports/2026-11-23-passed-review/`) and the private model and data cards.** `test-real` is a Phase 4 addendum |
| 2 | Website v1 | 🔄 **Started early (23 Nov 2026), in the separate JavaScript repo `ffwd-web` (D-047)**: home page, engine port with the conformance cases, ffmpeg.wasm `/app` flow with a scripted model, static pages and the analytics allowlist are built and tested. Not started: WebLLM/MLC model (Plan E), deployment |
| 3 | Helper app | ⬜ Not started |
| 4 | Science & polish | ⬜ Not started |
| 5 | Users & iteration | ⬜ Not started |

Update this table at the end of every phase. Each phase ends with a short `reports/<date>-phase-N/summary.md`.

**Timeline (part-time, around semester work):** Phase 0 ≈ 1 week · Phase 1 ≈ 10 days · Phase 2 ≈ 2 weeks · Phase 3 ≈ 1–2 weeks · Phase 4 ≈ 1–2 weeks · Phase 5 ongoing. Target: Phases 0–4 done by the end of 4th semester.

---

## Budgets

| Resource | Budget | Rules |
|---|---|---|
| **DeepSeek API** | **$4 total** | Pilot ≈ $0.25 · SFT teacher data ≈ $2.75 · DeepSeek baseline on held-out tests ≈ $0.75 · reserve ≈ $0.25. Use V4 Flash, off-peak for bulk, thinking off, max-token caps, identical prompt prefix for cache hits; **hard cap enforced in code**. Re-check prices and peak hours on the official pricing page before each bulk run (they changed several times in 2026) |
| **Kaggle GPU** | ~30 h/week, 12 h sessions | Prefer 2×T4. Checkpoint/resume always. Idle notebooks burn quota, so shut them down |
| **Paid Colab (optional)** | Owner decides | Fallback when the Kaggle quota blocks progress (T4/L4 hourly rates are low) |
| **Frontier agent subset** | Owner's Claude Code/Codex subscription | ~30–50 held-out tasks, run manually or scripted within plan limits |
| **Hosting** | $0 | Cloudflare Pages, Hugging Face Hub, PostHog free tier (1M events/month) |

---

## Phase 0: Go/no-go spike (≈1 week)

**Goal:** prove the core loop works, measure the gap, and resolve the blocking unknowns **before** heavy investment.

### Tasks
- [ ] Repo scaffold (monorepo layout per ARCHITECTURE §11), CI skeleton, `packages/protocol` v0 schemas
- [ ] Python environment: probe, allowlist validator, executor (temp dir, timeout), checker v0 (video/audio/time/size/frames/re-encode)
- [ ] Mini corpus: ~15 clips covering H.264, **HEVC (iPhone-style)**, MOV/MP4/WebM, rotation metadata, no-audio, quiet audio
- [ ] ~50 hand-written tasks across F1–F12 incl. 10 multi-step, 3 ambiguous, 3 unsupported (these spike tasks later join `dev`, **never** a test split)
- [ ] Baselines on the 50 tasks: **B1/B2 Qwen3-0.6B and 1.7B** (local or Kaggle) and **X1 DeepSeek V4 Flash** (pilot budget ≤ $0.25)
- [ ] **Browser feasibility checks:**
  - [ ] ffmpeg.wasm (multithreaded) builds and runs under COOP/COEP on Cloudflare Pages
  - [ ] **HEVC decode in ffmpeg.wasm** (blocking for F3)
  - [ ] ffprobe availability in the installed ffmpeg.wasm version
  - [ ] ~~WebLLM loads Qwen3-0.6B and 1.7B (prebuilt)~~ superseded (D-049/D-050): GGUF in the browser with wllama; measured on the owner's laptop 23 Nov 2026 (`reports/2026-11-23-browser-gguf`); still open: 1–2 other machines, integrated GPUs, Firefox/Safari
  - [ ] Peak tab memory: model + ffmpeg.wasm + 100 MB / 500 MB input
  - [ ] Seconds for 3 typical chores in the browser vs native
- [ ] Measure GPU-hours per GRPO step for a toy multi-turn run (≈10 steps) on Kaggle; confirm the training library's multi-turn support
- [ ] Read and save DeepSeek's current API terms re: training on outputs (date-stamped)

### Exit criteria (go/no-go)
- **GO** if: frontier success clearly exceeds base small model (e.g. ≥25 points on the 50 tasks; exact threshold recorded in `eval/PREREGISTRATION.md`), **and** the browser loop runs at least F1/F4/F7 end to end.
- **RETHINK** if: the base small model already scores ≥ ~85–90% (little to train), or WebLLM/ffmpeg.wasm can't run on typical laptops.
- **Decisions recorded:** browser-mode size limit, system requirements, HEVC path (browser vs helper-only), default model size candidates, compute plan.

---

## Phase 1: Core model (≈10 days with Claude Code)

**Goal:** a trained agent with an honest results table.

### Tasks
- [x] Task generator v1: templates for F1–F12, compositions (2–4 families), ambiguous/unsupported flags, paraphrases; **hash-pinned splits**
- [x] Corpus v1 (licence-clean, manifested; **any extra real clips (own recordings, real VFR/HDR) must be ingested BEFORE teacher generation: adding a clip changes the corpus hash and rebuilds every split, which would invalidate teacher data built on the old splits**); checker v1 (loudness, frame interval/count, offset, quality floor)
- [x] Conformance suite v1 (golden cases that both the Python and later TS checkers must pass)
- [x] Teacher generation: budget-guarded DeepSeek client; off-peak bulk on `train`; keep **only check-passing** trajectories; data card
- [x] Rejection sampling for easy tasks from base Qwen3 (free) (nothing to keep: stock Qwen3-0.6B scores 0/300 on dev)
- [x] SFT (LoRA → merged) for 0.6B (M1, dev 98%; 1.7B not started)
- [x] Multi-turn GRPO environment + one main run (checkpoint/resume), reward v1, telemetry logging (M3 = checkpoint-60 after the step-59 OOM and resume, D-045; the shuffled-reward control was not run)
- [x] Eval on dev → checkpoint selection → **single** run on test splits (22–23 Nov 2026, test lock held: 15 ledger rows for 5 systems × 3 splits)
- [x] Export GGUF (Q8_0 ships: M3 97/100 vs Q4_K_M 60/100 on the dev parity sample); simple CLI (`ffmpeg-agent "<request>" file.mp4`) using llama.cpp + native FFmpeg; parity eval
- [ ] Model + data card on Hugging Face

### Exit criteria
- Results table (EVALUATION §7) with CIs for B0, B2, M1, M3, X1 on test-iid + test-compositional
- Model on Hugging Face; CLI works on the owner's machine
- Phase report with honest limitations

---

## Phase 2: Website v1 (≈2 weeks)

**Goal:** the public, browser-first product.

### Tasks
- [x] Browser model decision and spike: MLC dropped (q4f16_1 2/100), **GGUF Q5_K_M through wllama passes the dev criteria on WebGPU** (96/100, 2.2 s per turn, 455 MB); [ ] Hugging Face model repo (public only after the DeepSeek terms review), [ ] one extra test-split row (plan in `reports/2026-11-23-browser-gguf/TEST_RUN_PLAN.md`, owner approval needed)
- [ ] `apps/web`: capability check, file input, model worker (wllama), FFmpeg worker (ffmpeg.wasm MT), TS agent loop + checker (**passes the conformance suite**)
- [ ] Spec confirmation UI, `ask_user` / `unsupported` UI, progress, preview, check summary, download / save-to-folder, "show command"
- [ ] Batch of small files via the File System Access API
- [ ] Cloudflare Pages with `_headers` (COOP/COEP), HTTPS, caching
- [ ] PostHog: anonymous config (no autocapture/replay, IP disabled), event list per ARCHITECTURE §9, dashboards
- [ ] Privacy page; system requirements page
- [ ] Playwright end-to-end tests (3+ chores) in CI
- [ ] 5 per-chore landing pages (pre-filled requests)

### Exit criteria
- Public URL; 3+ chore families pass end-to-end tests in Chrome/Edge
- Funnel visible in PostHog; no forbidden fields in event payloads (automated test)

---

## Phase 3: Helper app (≈1–2 weeks)

### Tasks
- [ ] FastAPI helper: health/probe/run/check/agent endpoints, loopback bind, Origin allowlist, pairing token, user-approved folders
- [ ] Manage prebuilt `llama-server` (GGUF) + static FFmpeg (pinned URLs + checksums); NVENC detection
- [ ] Site: helper detection, Local Network Access permission UX, automatic handoff for big files/batches
- [ ] Windows installer first; then Linux
- [ ] Security tests: cross-origin requests rejected, missing/invalid token rejected, path traversal rejected, shell metacharacters inert

### Exit criteria
- Big-file and 40-file batch chores work end to end on Windows
- Security tests pass in CI

---

## Phase 4: Science & polish (≈1–2 weeks)

### Tasks
- [ ] Ablations: single-turn vs multi-turn GRPO; seeds (as compute allows); 0.6B vs 1.7B
- [ ] Quantization study: fp16 vs MLC q4 vs GGUF Q4/Q8 (accuracy + speed)
- [ ] Browser vs native speed table by family/size
- [ ] DeepSeek baseline on all test splits (budget ≈ $0.75) + Claude Code/Codex subset
- [ ] test-real set (hand-written, real clips; owner-recorded clips, excluded from training, dev and the app's fixtures); ELLMPEG subset if allowed
- [ ] Sanity controls (shuffled reward, leakage audit, human spot-check)
- [ ] Final report, README results section, 60–90 s demo video, blog-style write-up

### Exit criteria
- Final report with all predeclared comparisons, CIs and limitations
- Resume bullets filled with real numbers

---

## Phase 5: Users & iteration (ongoing)

### Tasks
- [ ] Expand per-chore landing pages (target 20+)
- [ ] Answer real questions on Reddit/Super User/Stack Exchange (follow community rules)
- [ ] Launch posts (Show HN, relevant subreddits, student/creator communities)
- [ ] Monthly review: activated, 30/60-day returning, funnel drop-offs, unsupported categories → roadmap
- [ ] Ship smaller/faster model variants if the download step is the main drop-off

### Success signal
- Activated users growing month over month; a returning-user share that is stable or rising; the top unsupported categories addressed

---

## Phase 0 follow-ups (16 Nov 2026; results in `reports/2026-11-16-phase0-followups/`)

| # | Task | Status |
|---|---|---|
| T1 | Wilson CIs for single rates (D-021), tests vs scipy, regenerated table | ✅ done |
| T2 | Checker v1 A/V offset (first-packet timestamps), golden cases, X1 re-graded row | ✅ done (X1 48/50 re-graded) |
| T3 | Harness owns `-threads` cap; browser probe via `ffmpeg -i` parsing (measured vs ffprobe) | ✅ done |
| T4 | B0 regex baseline, fair base-model baselines, failure taxonomy (dev only) | ✅ done (B0 46/50 optimistic; fair rows no better) |
| T5 | Off-box checkpoints on a private HF repo (D-022), resume verifier, local kill-and-resume rehearsal | ✅ code + local rehearsal; ⏳ **Kaggle kill-and-resume run is the owner's step** (`training/grpo/kaggle_resume_test.ipynb`), plus the Qwen3-1.7B GPU-h/step measurement |
| T6 | Pass-rate task filter, reward v1 draft terms, per-step telemetry, shuffled-reward control | ✅ code only, no main run |
| T7 | Browser bench scripts, native bench, GPU policy flag (D-023, provisional) | ✅ scripts + desktop run; ⏳ other machines are the owner's step |
| - | Owner: review the 50 tasks (edits create `spike-v1`) | ⏳ open |
| - | Owner: run the bench on 1-2 other machines incl. an iGPU-only laptop | ⏳ open |
| V1 | spike-v1 (D-025): checker v1.2 implicit invariants, one rotation convention, frame-count rule, unsupported tasks without a family, m05 dropped; FFmpeg version parity proposed (D-024) | ✅ checker + tasks + 32 golden cases; ⏳ owner adds ~20 tasks + 2-3 clips, then B0/1.7B/X1 on spike-v1 |
| - | [ASK] before any teacher-data generation or the main GRPO run | gate |
