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

### D-021: Wilson score intervals for single success rates (16 Nov 2026)
- **Context:** the Phase 0 baseline table showed "0% [0%, 0%]" for base Qwen3-0.6B (0/50). A percentile bootstrap resamples only observed outcomes, so at 0/n or n/n every resample is identical and the interval collapses; the real uncertainty at 0/50 is about [0%, 7%].
- **Decision:** single success rates use the **Wilson score interval** (95%, no continuity correction). The paired percentile bootstrap stays only for paired differences between systems on the same tasks.
- **Alternatives:** Clopper-Pearson (exact, guaranteed >= 95% coverage but noticeably wider, e.g. 0/50 gives [0%, 7.1%] vs Wilson [0%, 7.1%] here but 4/50 [2.2%, 19.2%] vs [3.2%, 18.8%]); percentile bootstrap (degenerate at the extremes).
- **Why Wilson:** closed form (also trivial to port to the TypeScript site), good coverage for small n and for rates near 0 or 1, which is exactly where our baselines sit; reference values are tested against scipy's implementation.
- **Consequences:** Phase 0 tables are regenerated with Wilson in `reports/2026-11-16-phase0-followups/baselines-wilson.md` (the original report is unchanged). With n = 50, intervals are wide (about +-14 points near 50%); say so next to every headline number.

### D-022: GRPO checkpoints live on a private Hugging Face Hub repo (16 Nov 2026)
- **Context:** Kaggle wipes `/kaggle/working` when a session ends (idle timeout, crash, 12 h limit); the Phase 0 Kaggle run lost its checkpoints that way (D-015 only said "checkpoint/resume"). A resumable run needs the full HF Trainer checkpoint off-box: adapter weights, `optimizer.pt`, `scheduler.pt`, `rng_state.pth`, `trainer_state.json` (global step; the Trainer skips already-consumed batches on resume), plus our metrics file.
- **Decision:** after every save, push `checkpoint-N` as one commit to a **private HF Hub repo** (`JustJoyful/ffmpeg-agent-ckpt`, `checkpoints/checkpoint-N/`); `--resume` takes the newer of the local and remote checkpoint. Auth: a write token in the Kaggle secret `HF_TOKEN`.
- **Alternatives:** a Kaggle Dataset (notebooks cannot easily create new dataset versions mid-run; slow to iterate); Google Drive (auth friction); keeping only local checkpoints (what failed).
- **Why Hub:** one atomic commit per checkpoint (a half-uploaded one is never "latest"), free private storage, already used for final model weights (D-007), tokens/secrets work on Kaggle. LoRA checkpoints are about 130 MB, so the free quota is fine; for larger full-parameter runs add pruning (`keep_last`) first.
- **Verified:** locally by SIGKILL + fresh empty working dir + resume from the remote only (`training/grpo/rehearse_resume.sh`), and the real Hub push/restore path with a dummy checkpoint. The Kaggle kill-and-resume run is the owner's step (`training/grpo/kaggle_resume_test.ipynb`).
- **Consequences:** resume correctness is checked on deterministic quantities (step continuity, LR schedule), not noisy rewards (`training/grpo/verify_resume.py`). The Phase 0 figure of 0.071 GPU-h/step applies to **Qwen3-0.6B** only; the 1.7B figure is measured by the notebook's last cell.

### D-023: Discrete-GPU policy for browser model loading: warn-and-allow, PROVISIONAL (16 Nov 2026)
- **Context:** Phase 0 refused to load a model unless the WebGPU `high-performance` adapter was NVIDIA, because on the owner's hybrid laptop an iGPU fallback puts weights in system RAM (a crash risk on a 16 GB machine). Many target users have only an integrated GPU.
- **Decision (provisional, by owner instruction):** the policy is a flag in `spikes/browser/src/config.ts` (`DEFAULT_GPU_POLICY = "warn"`, override with `?gpuPolicy=refuse`). "warn" loads the model on an integrated GPU and records the warning; "refuse" keeps the Phase 0 behaviour. The final policy is decided from iGPU measurements (bench on an iGPU-only laptop).
- **Consequences:** until measured, an iGPU user may see slow inference or high RAM use; the bench records the adapter, load split and memory so the decision can use data. Not changed beyond the flag without owner approval.

### D-024: One FFmpeg across training, eval, helper, CLI and browser: PROPOSED (16 Nov 2026)
- **Context:** the browser runs ffmpeg.wasm core-mt 0.12.10 = **FFmpeg 5.1.4**; training/eval here run native **FFmpeg 9.0.2**. Measured in both (`reports/2026-11-16-spike-v1/wasm-ffmpeg-capabilities.json`, `e2e/ffmpeg-version.spec.ts`):
  - `-display_rotation` (lossless rotation by display matrix, in our allowlist and in B0/reference solutions) **does not exist in 5.1.4**: "Error splitting the argument list: Option not found".
  - `-metadata:s:v:0 rotate=90` works in 5.1.4 (display matrix 90.00, i.e. counterclockwise 90) and is **ignored by 9.0.2**. So no lossless-rotate command runs in both.
  - Native 9 also removed `-vsync` (use `-fps_mode`, which both have). `fps`/`select` frame counts, `transpose`, `-itsoffset` behave the same (frame-boundary counts are identical in both).
  - Consequence today: a trajectory using `-display_rotation` passes in training and checker but fails in the browser, so training data can teach commands the product cannot run.
- **Options:**
  - **A. Pin everything to the browser's FFmpeg 5.1.x** (static native build for training, eval, helper, CLI), and replace `-display_rotation` in the allowlist by the 5.1 spelling `-metadata:s:v:0 rotate=<ccw degrees>`. One semantics everywhere; the claim "what passes the checker runs in the browser" becomes testable by construction.
  - **B. Allowlist = intersection of both.** Cheap, but lossless rotate (PRD F5) becomes inexpressible; only re-encode via `transpose`.
  - **C. Per-runtime dialects.** The prompt names the runtime; the model learns two spellings. More data, more failure modes.
- **Recommendation:** A, plus a **dual-runtime conformance run**: the same recipes in `packages/protocol/conformance/checker-*.jsonl` run natively and in ffmpeg.wasm (the `runtimes` field already marks where a recipe is valid), and a conformance failure blocks merge (RULES §4.8).
- **Not yet verified:** a native 5.1.x binary was not run (download of a static 5.1.1 build was not permitted in this session; browser core is 5.1.4, a patch-level difference). Verification step: obtain 5.1.x, run `pytest tests/` and `eval.verify_tasks` against it, record differences. The corpus generator (synthetic clips, a one-off offline tool) may keep a newer FFmpeg as long as manifest hashes come from one pinned build.
- **Consequences if accepted:** allowlist change `-display_rotation` -> `-metadata ... rotate`; B0 (frozen at `b0-frozen-paraphrase`) keeps emitting `-display_rotation`, so B0 on browser-valid tasks is reported as "native-FFmpeg-9 dialect" or re-frozen deliberately as B0 v2; Phase 3 helper ships the same pinned build.

### D-025: spike-v1 and checker v1.2: implicit invariants, one rotation convention, frame-count rule (16 Nov 2026)
- **Context:** owner review of the 50 spike tasks found checker holes: a 0.1 s H.264 clip satisfied every field of s07 ("won't play in PowerPoint"); rotation had two meanings (probe vs spec) and direction was unverified; image-sequence counts hid boundary ambiguity behind a +-1 tolerance; unsupported tasks claimed a family. spike-v0 stays unchanged and is reported separately from spike-v1.
- **Decision:**
  - **Implicit invariants:** unless the spec changes them, output **duration** equals the input's (sum for a merge; +-0.1 s; plus |offset| when an A/V offset is set) and **audio presence** equals the input's; a `kind=video` output has a video stream, `kind=audio` an audio stream. "Spec changes them" = any `time.start_s/end_s` (also how speed tasks state a new duration) or `audio.present`.
  - **Rotation:** one convention, CLOCKWISE degrees. Spec: net rotation of the displayed picture vs the input's, measured from content (32x32 thumbnails, `training/env/orientation.py`), so metadata rotation and re-encoded pixels are judged alike and direction is verified (90 = turn right, 270 = turn left). Probe: clockwise degrees of the display matrix (ffprobe's counterclockwise value negated), in Python and TypeScript. The probe change only affects `hevc_rot90` in the corpus (270 now, was 90).
  - **Frame counts:** samples at t = k*interval, kept while t < duration - half a frame. Explicit `expected_count`: exact (tolerance 0, was 1). Interval only: the strict count, or one fewer when the last sample is within half an interval of the end (FFmpeg's `fps` filter drops that slot, `select` keeps it; both identical in 5.1.4 and 9.0.2). s19/s20/m03 now pin interval and count.
  - **Unsupported tasks:** `families = []`, nullable `nearest_supported` (all three null: nothing supported is close). `task.schema.json` allows an empty list only for unsupported tasks; spike-v0 still validates.
  - **Tolerances** (loudness, offset, duration, fps, orientation) are documented in `training/config.py` with measured evidence (e.g. offsets read 21.3 ms early on every reference = one AAC frame of priming).
- **Alternatives:** keep +-1 on counts (hides off-by-one errors); one tolerance for frames and a content check for rotation only on re-encodes (two rules for one field); verifying rotation from metadata only (misses `transpose`-based rotation, the common case).
- **Consequences:** spike-v1 reference solutions: 43/43 pass checker v1.2; 32 new golden cases (11 invariants, 12 rotation, 9 frame counts) in `packages/protocol/conformance/checker-{invariants,rotation,frames}.jsonl` (the TS checker must pass them in Phase 2). v0 numbers cannot be re-graded by v1.2 without changing their meaning; the spike-v0 s13 test is skipped with the reason recorded. Known limits: rotation is measured from the first frame (a heavily trimmed output could mis-measure); filter-made A/V offsets are still unverifiable (checker fails them rather than passing unverified).
- **Addendum (Phase 1 T4, checker v1.3):** size-target videos that keep the input's timeline and framing also need a **quality floor** (SSIM >= 0.90 and PSNR >= 28 dB against the input, sampled at 2 fps; an explicit `quality` spec field overrides). Measured: 1 Mbps re-encode 0.98 / 38 dB, crf 45 0.95 / 33 dB, a 64x36 picture upscaled (the cheap way to hit a cap) 0.84 / 23 dB, a blank picture 0.40 / 7 dB; PSNR is what catches the tiny-picture hack that SSIM alone lets through. Trimmed or reframed size tasks (e.g. m01) are exempt from the *default* floor because their frames are not comparable: a **known gap** (a degenerate picture can pass there; the plan's reward guards and the human spot-check cover it, and an explicit `quality` field closes it per task). 6 golden cases in `checker-quality.jsonl`.

### D-026: One agent chat template for training and every runtime; spec-first prompt v1 (16 Nov 2026)
- **Context:** the GRPO rollout stream (`TokenPolicy`) keeps Qwen3's empty `<think>\n\n</think>\n\n` block in **every** assistant turn, but stock Qwen3 templates (HF, llama.cpp `--jinja`, WebLLM) render earlier assistant turns **without** it and add it only to the newest generation prompt. Measured with the HF tokenizer: for turn 2 the stock render has the block once, the training stream twice. The model would train on contexts it never sees at inference (and the Phase 0 toy GRPO had this mismatch). Separately, reward v1 has a `spec_acc` term and D-008 needs a model-emitted spec for the user to confirm, but prompt v0 had no `spec` action.
- **Decision:**
  - Ship **one chat template** (`packages/protocol/prompts/chat-template.jinja`): stock Qwen3 non-thinking minus tools/reasoning, with the empty think block on every assistant turn. Install it on the tokenizer for SFT/GRPO and embed it in every export (GGUF metadata or `--chat-template-file`; MLC `conv_template` in Phase 2 [VERIFY that the prebuilt `model_lib` accepts an assistant prefix]). SFT streams are built by replaying the conversation through `TokenPolicy`, so SFT and GRPO streams are byte-identical.
  - **Prompt v1** (`system-v1.txt`): short, no copyable example JSON, defines the `spec` action and fields, and the loop option `require_spec` rejects a `run` before a `spec` (invalid turn, not counted as a run). `ask_user` and `unsupported` remain allowed first. Prompt v1 stays a **draft** (`SYSTEM_PROMPT_V1_SHA256 = None`) until D-024 settles the lossless-rotate spelling; teacher generation must refuse a draft.
- **Verified:** Python render == Jinja render == HF `apply_chat_template` == llama.cpp `/apply-template` byte for byte (llama-server b12032 with `--chat-template-file`), SFT stream == tokenization of the rendered text, assistant-only mask. Goldens: `packages/protocol/conformance/chat-template.json` (the TS runtime must reproduce them).
- **Alternatives:** per-turn SFT examples under the stock template (exact at inference, but GRPO's one-stream-per-rollout contract cannot express per-turn samples); keeping stock templates and accepting the mismatch (silent train/inference skew, the failure Review Focus 1 warned about).
- **Consequences:** eval configs for models trained here must not pass `chat_template_kwargs.enable_thinking` and must load the agent template; baselines that use stock models (B1/B2/X1) keep the stock template. Phase 0 numbers are unaffected (all used stock templates).
