# DECISIONS: ffmpeg-agent decision log

Format: **context → decision → alternatives considered → consequences.** Newest decisions go at the bottom. To change a decision, add a new entry that supersedes the old one; don't edit history.

---

### D-001: Project domain: natural-language FFmpeg agent (14 Nov 2026)
- **Context:** I needed a project that adds LLM post-training, agent training, serving and real users to a resume that already has a research study (Testcard), RAG/agents (AxiomLM), streaming audio (S.P.E.A.K.) and data ingestion (VGC-Telemetry).
- **Decision:** a natural-language video-chore tool powered by a self-trained FFmpeg agent.
- **Alternatives:**
  - **SMS expense tracker:** dropped. Open-source on-device apps (PennyWise AI, Cashiro) already exist and parse SMS with regex, Account Aggregator apps (e.g. Fold) make SMS reading unnecessary for many users, and AI wasn't needed for the core job.
  - **Text-to-SQL:** too crowded with GRPO papers.
  - **Textbook math in AxiomLM:** least distinctive.
  - **Receipt splitter and Hinglish voice:** not chosen.
- **Consequences:** AI is genuinely needed (rules can't cover the long tail); outputs are machine-verifiable, which suits RL.

### D-002: Positioning vs frontier coding agents (14 Nov 2026)
- **Context:** Claude Code/Codex already do FFmpeg edits well, including batches, and many people pay for them.
- **Decision:** don't claim to beat them. Position the product for **non-developers** (no terminal, no subscription) and the research as **"small specialist agent vs frontier agent"**, with frontier agents as explicit baselines.
- **Alternatives:** pivot to batch editing as the differentiator (rejected: coding agents already handle batches).
- **Consequences:** modest, occasional-use user numbers are expected; the research claim is about accuracy-per-cost and locality.

### D-003: Long-tail chores, not platform presets (14 Nov 2026)
- **Context:** "fit it for WhatsApp" is weak (WhatsApp recompresses video itself), and common one-click jobs are well served by presets/regex tools (e.g. Ez FFmpeg).
- **Decision:** target the **long tail of occasional chores** (frame extraction, iPhone compatibility, A/V offset, merges, lossless rotate, loudness, batch trims) and multi-step combinations.
- **Consequences:** chore families F1–F12 (PRD §5); a regex/preset baseline is included to show where AI actually helps.

### D-004: Multi-turn GRPO in the live tool loop (14 Nov 2026)
- **Context:** a NeurIPS 2026 study found single-turn RLVR gave no gain over SFT for small tool agents; multi-turn GRPO with the real tool loop executed during rollouts produced large gains (2B: 4.3% → 58.7%). CacheRL (2026) found data and reward design matter more than the optimiser.
- **Decision:** SFT on verified trajectories → **multi-turn GRPO** with execution-verified rewards; single-turn GRPO kept as an ablation.
- **Consequences:** heavier rollouts (FFmpeg runs per turn) → checkpoint/resume and careful compute budgeting; a null result is acceptable and will be reported.

### D-005: Browser-first product; helper app for power users (14 Nov 2026)
- **Context:** hosting GPU inference costs money; users want nothing installed and nothing uploaded.
- **Decision:** the main product runs entirely in the browser (WebLLM + ffmpeg.wasm). An optional native helper (FFmpeg + llama.cpp) handles big files, batches and GPU encoding.
- **Alternatives:**
  - a hosted GPU service (cost; privacy)
  - helper-only (install friction)
  - browser-only (ffmpeg.wasm is ~10–100× slower than native, has a ~2 GB memory cap and no GPU encode)
- **Consequences:** zero marginal hosting cost; there's no server-side "concurrent users" story, so serving skills are shown via the browser/native benchmarks and an optional vLLM load test.

### D-006: Desktop/laptop only in v1 (14 Nov 2026)
- **Context:** WebGPU and ffmpeg.wasm are weak on phones (memory, GPU support).
- **Decision:** v1 supports desktop/laptop Chrome/Edge; published system requirements; a clear message on mobile.
- **Consequences:** mobile is revisited only with measurements.

### D-007: Model family Qwen3 0.6B / 1.7B, reusing WebLLM prebuilt libraries (14 Nov 2026)
- **Context:** each visitor downloads the model once; WebLLM ships prebuilt Qwen3 runtime libraries.
- **Decision:** fine-tune Qwen3-0.6B (and 1.7B if compute allows). For the browser, convert merged weights with `mlc_llm convert_weight`/`gen_config` using the prebuilt quantization and template, and reuse the prebuilt `model_lib`. Compile our own WebGPU library only if the architecture, vocab or quantization changes.
- **Consequences:** no custom engine work; the default size is decided by accuracy + model-load drop-off.

### D-008: User-confirmed spec; checker is code (14 Nov 2026)
- **Context:** at runtime there is no gold spec, so a model could check its own work too leniently.
- **Decision:** the model emits a spec; the UI shows it in plain language for confirmation; a deterministic checker verifies outputs against the confirmed spec. Training rewards use generator gold specs. Spec extraction is trained and evaluated separately.
- **Consequences:** an extra confirmation step in the UX; a much stronger correctness guarantee.

### D-009: `ask_user` and `unsupported` actions (14 Nov 2026)
- **Context:** requests can be ambiguous ("trim 0:30 to 1:00") or out of scope ("remove the person").
- **Decision:** two explicit actions, included in task generation and rewards (with penalties for unnecessary asks/refusals).

### D-010: Teacher = DeepSeek V4 Flash (budget $4); fallback = rejection sampling (14 Nov 2026)
- **Context:** frontier providers' terms may restrict training on outputs; I have ~$4 of DeepSeek credit. Sources indicate DeepSeek's terms allow using outputs for training/distillation, but one tracker reports a restrictive clause.
- **Decision:** DeepSeek V4 Flash as teacher for hard/multi-step tasks (off-peak, thinking off, cache-friendly prompts, hard cap), after reading and saving the current terms. Free rejection sampling (base Qwen3 / 4-bit 8–14B open model on Kaggle) for easy tasks and as a fallback. Claude Code/Codex are used **only as evaluation baselines**.
- **Consequences:** budget split pilot $0.25 / SFT $2.75 / baseline $0.75 / reserve $0.25; Kaggle quota is saved for GRPO.

### D-011: Hosting on Cloudflare Pages (14 Nov 2026)
- **Context:** multithreaded ffmpeg.wasm needs `SharedArrayBuffer` → COOP/COEP headers; GitHub Pages can't set custom headers.
- **Decision:** Cloudflare Pages with `_headers`; model weights on Hugging Face; helper releases on GitHub Releases.

### D-012: Anonymous PostHog analytics (14 Nov 2026)
- **Context:** I need real user numbers without accounts or personal data.
- **Decision:** PostHog anonymous events only (no identify, no autocapture/replay, IP capture disabled, localStorage persistence). Headline metrics: activated users, 30/60-day returning %, monthly actives, funnel. A monthly rhythm suits an occasional-use utility.
- **Consequences:** undercounting from ad blockers (optional reverse proxy); cleared storage or a different browser shows up as a new user.

### D-013: Helper security model (14 Nov 2026)
- **Decision:** loopback-only bind, Origin allowlist, pairing token, user-approved folders, structured arguments only, protocol version checks. Chrome's Local Network Access prompt is expected and explained in the UX.

### D-014: Distribution via per-chore pages and real questions (14 Nov 2026)
- **Context:** users search online for their exact chore.
- **Decision:** one landing page per chore (pre-filled tool), answering real questions in communities (following their rules), launch posts once ~20 chores are reliable, and a demo video.

### D-015: Kaggle for training, with checkpoint/resume (14 Nov 2026)
- **Context:** ~30 GPU-h/week, 12 h sessions, older GPUs (no bf16/FlashAttention 2).
- **Decision:** Kaggle as primary (prefer 2×T4), resumable training from day one, paid Colab as an optional fallback; GPU-hours per GRPO step measured in Phase 0.

### D-016: Open source under GPL-3.0 (14 Nov 2026)
- **Context:** the browser build distributes an FFmpeg core containing GPL components (e.g. x264).
- **Decision:** the whole project is GPL-3.0. Model weights are released under terms compatible with the base model licence (verify at release).

### D-017: 10-day core-model milestone; website follows (14 Nov 2026)
- **Context:** I want fast progress with Claude Code, but compute and RL debugging are wall-clock bound, and I must understand the work well enough for interviews.
- **Decision:** Phase 1 (≈10 days) delivers the trained model, results table and CLI. The website (Phase 2) follows. Phase 0 go/no-go comes first.

### D-018: Multi-turn GRPO library: TRL `rollout_func` (ACCEPTED by owner 15 Nov 2026)
- **Context:** D-004 requires GRPO with the real tool loop executed during rollouts. Phase 0 must measure GPU-hours per step on Kaggle 2×T4. Checked TRL docs (Nov 2026): `GRPOTrainer` supports environments two ways. `environment_factory` takes a class whose public methods become *native tool calls*, and the trainer runs the multi-turn loop. `rollout_func` lets us own generation and the environment loop entirely.
- **Decision:** TRL `GRPOTrainer` with **`rollout_func`**, wrapping the existing `training/env/loop.run_episode` so training, evaluation and the browser all share one JSON action protocol (ARCH §3.1) and one checker.
- **Alternatives:**
  - **TRL `environment_factory`:** least code, but actions become Qwen3 native tool calls, so the training format would diverge from the JSON actions the browser parses (an ARCH §3.1 change, and a WebLLM function-calling dependency).
  - **verl (multi-turn) / OpenPipe ART:** strong multi-turn support but heavier stacks; T4/fp16 support and Kaggle setup unverified.
- **Consequences:** we write ~100 lines of rollout code (generation via TRL's vLLM integration [VERIFY on T4/fp16]), and the same `score()` drives reward and eval. If `rollout_func` proves unworkable on T4, fall back to `environment_factory` and record a superseding decision.

### D-019: ffmpeg.wasm core loaded from a pinned CDN, not self-hosted (16 Nov 2026)
- **Context:** Cloudflare Pages rejects files over 25 MiB; `ffmpeg-core.wasm` (core-mt 0.12.10) is 31.2 MiB. Wrangler 4.162 also delegates new Pages projects to Workers unless `--force` is used (D-011 chose Pages).
- **Decision:** production loads the core from `cdn.jsdelivr.net/npm/@ffmpeg/core-mt@0.12.10` through `toBlobURL` (blob URLs are same-origin, so the pthread workers stay inside COOP/COEP; jsDelivr sends CORS headers, so it works under `credentialless`). Dev and local e2e use a local copy. The wasm is stripped from `dist`.
- **Alternatives:** chunking the wasm (complex, fragile); Workers static assets or R2 (same size limits / extra service); a custom smaller core build.
- **Consequences:** browser mode depends on a third-party CDN that sees visitor IPs, which the privacy page must state in Phase 2; the downloaded binary is not hash-verified yet. Phase 2 should self-host a compressed or chunked core, or add an integrity check.

### D-020: Phase 0 verdict: GO (16 Nov 2026)
- **Context:** preregistered rule (eval/PREREGISTRATION.md): GO if X1 - best base >= 25 pts and the browser loop runs F1/F4/F7 end to end.
- **Decision:** GO. X1 94% vs best base 8% (+86 pts, CI +76 to +94); the browser loop passes F1/F4/F7 with a scripted model on the live site; HEVC decodes in ffmpeg.wasm; toy GRPO runs on a T4 at 0.071 GPU-h/step (upper bound).
- **Open:** browser input-size limit and peak memory unmeasured; 1.7B never loaded in the browser; only one machine; task set owner review pending.
- **Consequences:** Phase 1 starts. First wins to build: a prompt without copyable examples (or SFT on verified trajectories), vLLM generation, checkpoint upload off Kaggle, checker v1 offset measurement. See reports/2026-11-15-phase-0/summary.md.
