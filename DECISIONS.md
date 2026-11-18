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
- **Verified:** locally by SIGKILL + fresh empty working dir + resume from the remote only (`training/grpo/rehearse_resume.sh`), and the real Hub push/restore path with a dummy checkpoint. The Kaggle kill-and-resume run was run by the owner on 16 Nov 2026 (see the Kaggle result below) (`training/grpo/kaggle_resume_test.ipynb`).
- **Kaggle result (16 Nov 2026, 8-step toy GRPO, Qwen3-0.6B):** session 1 trained and pushed `checkpoint-2`, `checkpoint-4`; the session was stopped and the notebook re-run with `MODE='resume'` (working dir and `/kaggle/working/ckpt` removed first); `checkpoint-6` and `checkpoint-8` appeared on the Hub. In `checkpoint-8`: `global_step` 8 = `max_steps`; `log_history` steps 1-4 are byte-identical to `checkpoint-4`'s and steps 5-8 follow (no step repeated or skipped); `toy_metrics.jsonl` rows 1-4 identical; LR 6.25e-06 at step 4 then 5e-06 at step 5 (scheduler state restored). The notebook's own `verify_resume` printed `"ok": true`, `"problems": []`, `"steps": [1..8]` (owner pasted the console output). Remaining caveat: the Hub files cannot prove the local checkpoint dir was empty at resume; that rests on the notebook edit. Measured cost in this run: about 0.062 GPU-h per step (steps 5-8, Qwen3-0.6B toy GRPO), under the 0.071 Phase 0 figure.
- **Consequences:** resume correctness is checked on deterministic quantities (step continuity, LR schedule), not noisy rewards (`training/grpo/verify_resume.py`). The Phase 0 figure of 0.071 GPU-h/step applies to **Qwen3-0.6B** only; the 1.7B figure is measured by the notebook's last cell.

### D-023: Discrete-GPU policy for browser model loading: warn-and-allow, PROVISIONAL (16 Nov 2026)
- **Context:** Phase 0 refused to load a model unless the WebGPU `high-performance` adapter was NVIDIA, because on the owner's hybrid laptop an iGPU fallback puts weights in system RAM (a crash risk on a 16 GB machine). Many target users have only an integrated GPU.
- **Decision (provisional, by owner instruction):** the policy is a flag in `spikes/browser/src/config.ts` (`DEFAULT_GPU_POLICY = "warn"`, override with `?gpuPolicy=refuse`). "warn" loads the model on an integrated GPU and records the warning; "refuse" keeps the Phase 0 behaviour. The final policy is decided from iGPU measurements (bench on an iGPU-only laptop).
- **Consequences:** until measured, an iGPU user may see slow inference or high RAM use; the bench records the adapter, load split and memory so the decision can use data. Not changed beyond the flag without owner approval.

### D-024: One FFmpeg across training, eval, helper, CLI and browser: ACCEPTED, option A (17 Nov 2026)
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
- **Acceptance (17 Nov 2026):** the owner's review approved D-029 with "the pinned static FFmpeg follows D-024 (5.1.x, browser parity). The checker always runs on the pinned build, everywhere." I read that as accepting option A (5.1.x everywhere, `-display_rotation` replaced by the 5.1 metadata spelling). Chosen build: John Van Sickle static 5.1.1 amd64 (GPL), tarball sha256 `2d848c37f7f276be0262d9123a84fbfe72bb159921ffcce3bd7106f143d29f42`, downloaded to `~/.cache/ffmpeg-pin-dl/`. **Owner decision (17 Nov 2026):** option A confirmed; look for a 5.1.4 static build first; if none exists, keep 5.1.1, record the gap here and add a parity test (every conformance case on native 5.1.1 and ffmpeg.wasm 5.1.4, checker results compared). **5.1.4 search result:** no static linux-amd64 5.1.4 binary is published (the publisher's `old-releases/` lists 5.0.1, 5.1.1, 6.0; searches found only the n5.1.4 source tag and build scripts), so **the pin is 5.1.1 and the native/browser gap is a patch-level difference 5.1.1 vs 5.1.4**, covered by the parity test (`tests/parity/`, runs when both runtimes are available; a mismatch blocks merge, RULES 4.8). The owner verifies the publisher's checksum and runs the extraction. **Status of the work:** downloaded and hashed, but extracting and running it was blocked by the sandbox classifier, so the pin is not yet active (no version check, no rebuild of splits, `LOSSLESS_ROTATE_SPELLING` still `display_rotation`). Owner action: run the extract-and-version command given in `reports/PHASE1-STATUS.md`.
- **Not yet verified (superseded 19 Nov 2026, see "Pin active"):** a native 5.1.x binary was not run (download of a static 5.1.1 build was not permitted in this session; browser core is 5.1.4, a patch-level difference). Verification step: obtain 5.1.x, run `pytest tests/` and `eval.verify_tasks` against it, record differences. The corpus generator (synthetic clips, a one-off offline tool) may keep a newer FFmpeg as long as manifest hashes come from one pinned build.
- **Pin active (19 Nov 2026).** Trust model: **trust on first use.** The publisher (johnvansickle.com) provides no checksum for the old-release 5.1.1 build; the owner downloaded it over HTTPS and verified that sha256 `2d848c37...9f42` matches the one recorded here. That hash is pinned in `config.FFMPEG_PIN`; `training.env.ffmpeg_pin install` refuses any tarball that does not match, and **every machine (local, Kaggle, CI) verifies it before use**. The installed binary reports `5.1.1-static`, which `require_pinned` compares verbatim; `FFMPEG_PIN_ENFORCED = True`, so any other FFmpeg is refused. Installing and running it uncovered these 9.0.2 -> 5.1.1 differences, all fixed: (1) `-display_rotation` does not exist: `LOSSLESS_ROTATE_SPELLING = "metadata_rotate"`, the corpus's rotated clips use `-metadata:s:v:0 rotate=90` (output option, counterclockwise; verified rotate=N gives probe rotation (-N) mod 360), conformance cases 6-9 and the references of spike-v1 s13/s14 were respelled (specs and verdicts unchanged; spike-v0 is frozen, s14 added to its documented waivers); (2) the `ebur128` option value `framelog=quiet` does not exist in 5.1: the filter graph failed and the failed run printed a zero summary that the checker read as **0.0 LUFS**; fixed with `framelog=-8` (valid in both) and a non-zero exit now means "unmeasurable" (None); (3) loudness of the same file is identical on both builds (-21.8 LUFS). Still open: remove `-display_rotation` from `allowlist.json` (protocol change: bump `protocol_version`, TS validator, validator conformance case 4); the native-vs-wasm parity test; a build of exact 5.1.4 (proposed below, not started).
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

### D-027: Split design: content hashing, held-out family combinations, held-out phrasing styles, clips split by clip (APPROVED with changes, 17 Nov 2026)
- **Decision:** a task's split comes from a hash of its *content key* (inputs + gold spec), never from its wording, so paraphrases of one content cannot straddle train and test. test-compositional holds out whole family *combinations* (`config.HELDOUT_COMBOS`). test-phrasing uses held-out phrasing *styles* that exist only in `phrasing_heldout.py`: **`context_first`** (a situation first, then the problem; replaces the originally proposed `technical`) and `indirect`. B0 v2 is authored from train phrasing only. **Owner change (b): real clips are split by clip before any task is generated**: a clip with manifest role `test-real` is used only by test-real tasks, the generator skips it, `add_clip` requires an explicit `--role`, and a CI test (`tests/taskgen/test_clip_roles.py`, with a planted-violation case) fails if a test-real clip id appears in any other split, including the spike tasks.
- **Why:** split by content hash is deterministic and leak-proof against paraphrase; held-out combinations test composition rather than memorised pairs; clip-level split stops a model from recognising a specific real clip's content across train and test.
- **Consequences:** the new styles were written before B0 v2 exists (same engineer); B0 v2 is written afterwards from train banks only and its source must not reference the held-out module. `context_first` and `indirect` reuse train core/symptom wording inside a new framing, so test-phrasing measures framing robustness, not new vocabulary (stated in the preregistration).

### D-028: M1/M3 are evaluated through merged GGUF in llama.cpp (APPROVED, 17 Nov 2026)
- **Decision:** the evaluated models are the merged LoRA checkpoints exported to GGUF and served by llama.cpp (the deployment path), with the one agent chat template (D-026), not HF `generate`.
- **Owner condition:** every Phase 1 report and model card states that the numbers are for the **native GGUF path**; the **browser (MLC q4f16_1) number comes from the Phase 2 parity check**.

### D-029: Corpus as a hash-verified tarball; the pinned static FFmpeg follows D-024 (APPROVED, 17 Nov 2026)
- **Decision:** the corpus is distributed as a hash-verified tarball in a private HF dataset repo (real clips are not regenerable). The pinned static FFmpeg is **5.1.x** (D-024, browser parity), and **the checker always runs on the pinned build, everywhere** (local, Kaggle, CI, helper). Implementation items: fail-closed version assertion, Kaggle kernel installs the pinned build instead of apt FFmpeg, FFmpeg version in the task-verification cache key (done), `LOSSLESS_ROTATE_SPELLING` switched, then splits rebuilt and the dev baselines re-run if dev results change.

### D-030: Test-run lock (APPROVED, 17 Nov 2026)
- **Decision:** a test split is evaluated once per (system, checkpoint, split); a rerun needs a logged `--supersede-reason` (`eval/testlock.py`, `reports/TEST_RUNS.jsonl`). The lock refuses every test run until the preregistration marker reads `Phase 1 status: FINAL`.

### D-031: Phase 1 systems: M2 deferred, 1.7B is a stretch (APPROVED, 17 Nov 2026)
- **Decision:** the Phase 1 table is B0, B2, M1, M3, X1. M2 (single-turn GRPO ablation) moves to Phase 4. Qwen3-1.7B: SFT first; GRPO only if the 0.6B result and the measured 1.7B GPU-h per step justify it.

### D-032: Programmatic "oracle" trajectories as an SFT source (APPROVED with conditions, 17 Nov 2026)
- **Context:** the task generator emits, for every task, a verified gold spec and a verified reference command. Playing them through the agent loop (spec, run, finish; `ask_user` for ambiguous; `unsupported` for unsupported) yields perfect trajectories for free (`training/teacher/oracle.py`). The primary teacher stays DeepSeek V4 Flash (paid, $4 cap, gated).
- **Decision (owner):** (a) oracle trajectories are used now for end-to-end pipeline smoke tests with no spend; (b) they may join the real SFT mix with a **share cap of at most 30%** (`config.SFT_ORACLE_SHARE_MAX = 0.30`), tagged `source=oracle` in the data card and on every example; (c) they are the **fallback** if the teacher budget runs out (the cap is then lifted explicitly with `--oracle-fallback`, recorded as `oracle_cap_lifted` in `stats.json`); (d) **M1-oracle** (SFT on oracle data only, `--oracle-only`) is a **dev-only ablation** against M1-teacher, reported descriptively and outside Holm; `eval/testlock.py` refuses `M1-oracle*` on any test split.
- **Trade-offs:** oracle data is canonical (one solution per content, lossless-first, no recoveries from failed runs), so it teaches format and the spec contract well but little error recovery; DeepSeek trajectories include real retries. Both are legitimate on `train` only, never on dev/test (the generators refuse other splits).

### D-033: Real-clip ingestion: roles vs tags, restricted clips, declared A/V skew (APPROVED plan, 19 Nov 2026)
- **Decision:** the owner's property labels (`h264-landscape`, `merge-part`, `cinema-aspect`, `4k`, ...) are manifest **tags** (snake_case, next to the existing property tags `rotation`, `portrait`, `webm`, `prores`, `vfr`, `av_offset`, `no_audio`, `quiet_audio`), not `--role` values: `role` stays `taskgen | test-real` (D-027b). Clips are built by `training/corpus/ingest_sources.py` from the declarative `sources.json`; a label whose property the probe does not confirm is rejected (RULES 4.1), which is how Cosmos/Meridian were found not to be HDR and the "noaudio" screen recording to carry a silent AAC track. Own recordings are `test-real`; downloaded and derived clips `taskgen`. `restricted: true` clips (Meridian, licence unverified) are skipped by `ClipIndex` for every split until the owner confirms the licence.
- **A/V skew:** a `-c copy` cut of the ToS sources adds 42-77 ms of first-packet skew (B-frame and mp3 timestamps; the sources are aligned). The checker's +-40 ms offset window is absolute, so such clips are tagged `av_skew`, record `measured_offset_ms`, and F11 never draws them (a gold of 0 ms or 500 ms would not hold). Any clip over 25 ms must carry the tag or ingestion refuses it.
- **Probe fix:** `avg_frame_rate` can be junk (`30000/1` on a 60 fps VP8 webm); `stream_fps` falls back to `r_frame_rate` above `PROBE_MAX_FPS`. The TypeScript probe must do the same before Phase 2 parity (conformance case to add).
- **Consequences:** adding clips changes `corpus_manifest_sha256`; splits are rebuilt once (planned with the FFmpeg pin) and any later real clip must be ingested before teacher generation (PHASES.md). Cuts were made with ffmpeg 9.0.2 (recorded per clip); mov/mp4 cuts rebuild byte-identically, webm/mkv rebuild with the same packets but different muxer ids. Corpus media goes to the private HF dataset only; the whatsapp clip has faces (friend consented) and must never appear in public demos or samples.

