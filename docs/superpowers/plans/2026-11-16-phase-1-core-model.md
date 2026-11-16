# Phase 1 Core Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Gate tasks (marked [ASK]) stop and wait for the owner; never start them on your own.**

**Goal:** Produce a trained 0.6B FFmpeg agent (SFT, then multi-turn GRPO) with an honest results table (B0, B2, M1, M3, X1 on test-iid, test-compositional, test-phrasing, test-real, with CIs), a GGUF export that passes a parity eval, a working `ffmpeg-agent` CLI, and model/data cards on Hugging Face.

**Architecture:** Reuse the Phase 0 harness unchanged in shape (validator → executor → checker, one JSON action per turn, gold spec for rewards). New work is (1) a real task generator with hash-pinned splits and a stronger corpus/checker, (2) a frozen prompt/chat-template so teacher data, SFT, GRPO, eval and the CLI all see byte-identical formats, (3) teacher + rejection-sampled trajectories → LoRA SFT on Kaggle, (4) batched ("lockstep") multi-turn rollouts for GRPO with off-box checkpoints, (5) one preregistered, single-shot test run enforced in code. Evaluation of M1/M3 runs locally through llama.cpp GGUF, the same path the deployed model uses, so `eval.run_baseline` is reused as is.

**Tech Stack:** Python 3.11 (uv, pytest, Ruff, Black), TRL 1.18 `rollout_func` + PEFT + transformers 5.x (Kaggle T4, fp16), llama.cpp b12032 (Vulkan locally) for GGUF eval, FFmpeg (one pinned static build), DeepSeek V4 Flash through `training/teacher/budget.py`, Hugging Face Hub (private repos), Kaggle CLI via `training/grpo/kaggle_kernel.py`.

**Spec:** `PHASES.md` (Phase 1 + budgets), `ARCHITECTURE.md` §3, §6, §7, `EVALUATION.md` §2–§7, `RULES.md`, `DECISIONS.md` D-004, D-007, D-008, D-009, D-010, D-015, D-018, D-021, D-022. Phase 0 evidence: `reports/2026-11-15-phase-0/`, `reports/2026-11-16-phase0-followups/`, `reports/2026-11-16-paraphrase-robustness/`.

## Status (17 Nov 2026)

| Item | State |
|---|---|
| Owner plan review | Done 17 Nov: D-027 (changed), D-028, D-029, D-030, D-031 approved; D-032 pending the owner's decision |
| Phase | **In progress** (`PHASES.md`) |
| Gate G0a Kaggle kill-and-resume | **Satisfied** (16/17 Nov, `verify_resume` ok, D-022). It blocks T16+ only, never T1-T15 |
| Built (T1-T15 code and local smoke tests) | Corpus, checker v1.3, taskgen + splits, chat template, SFT/GRPO/export code; dev baselines B0 53% and stock Qwen3-0.6B 0% on dev v1 |
| Open engineering item | D-029 pin: 5.1.1 static build downloaded (sha256 in D-024) but not yet runnable here (sandbox classifier); splits are rebuilt after the pin |
| Paid steps | None open. G-terms (terms file + off-peak window) must exist before any DeepSeek call |

## Global Constraints

Copied from the spec and `training/config.py`; every task includes these implicitly.

- Python 3.11+, uv lockfile, Ruff + Black clean, type hints on public functions; TypeScript strict if touched. One config source per package (`training/config.py`): **no magic numbers in modules**.
- **Commits:** `type(scope): description`, one commit per task, **no `Co-Authored-By` and no Claude/AI attribution** (CLAUDE.md overrides any default).
- **No shell strings** anywhere; allowlist validator before every FFmpeg run; the model never sees real paths.
- Turn budget: ≤ `MAX_RUNS_PER_JOB = 4` runs, `MAX_TURNS_PER_JOB = 8`, `MAX_ASK_USER = 1`. `check` is run by the harness, not the model.
- Rewards use the **gold spec**; runtime/CLI checks use the **user-confirmed spec** (D-008). Never swap them.
- Reward v1 weights (`REWARD_WEIGHTS`): pass 1.0, partial 0.3, spec_acc 0.2, efficiency 0.1, clarify ±0.5, invalid −0.5 per invalid action (cap `REWARD_INVALID_CAP = 4`). Tune on **dev only**.
- Task-filter band `PASS_RATE_BAND = (0.2, 0.8)`, `PASS_RATE_SAMPLES = 8`, allowed on `train`/`toy` only.
- Checker tolerances: time 0.1 s default, fps 1 %, frame count ±1, loudness ±2.0 LU, A/V offset ±40 ms from first-packet pts (window 16 packets).
- **Splits** (targets, `EVALUATION §2`): train thousands, dev ≈300, test-iid ≈500, test-compositional ≈200, test-phrasing ≈200, test-real ≈100. Hash-pinned; test splits never used for training, tuning, few-shot, teacher prompts, paraphrase seeds, reward tuning or checkpoint selection.
- **Budget:** DeepSeek **$4 lifetime** hard cap in code (spent so far ≈ $0.056, `data/budget-ledger.jsonl`); every paid call through `BudgetGuard`; pilot ≤ 20 tasks before any bulk; bulk off-peak, thinking off, byte-identical prompt prefix, log cache hit/miss tokens. Kaggle ≈ 30 GPU-h/week, 12 h sessions, T4 fp16 (no bf16), always checkpoint to the HF Hub (D-022).
- **Statistics:** Wilson 95 % for single rates (D-021); paired percentile bootstrap (10,000 resamples, seed `BOOTSTRAP_SEED = 20261115`) for system differences; **Holm** across the preregistered comparison family; failed/timed-out/malformed runs stay in denominators; report by family and difficulty; ≥3 GRPO seeds only if compute allows, otherwise say "single seed".
- Reports go to fresh `reports/<date>-<milestone>/` dirs with `manifest.json` (commit, versions, hashes, hardware, seeds, costs); never overwritten.
- Tokens: `HF_TOKEN`, `DEEPSEEK_API_KEY` only from env / gitignored `.env`; secret-scan test stays green.
- Model names follow `agent-v{major}.{minor}-{size}`. Licence of every clip/model/dataset recorded before use.

## Review Focus

Failure modes the spec implies but no task would otherwise exercise, most likely to bite first. Each has a pinning test in the task named in brackets.

1. **Chat-template mismatch** between HF training, llama.cpp and (Phase 2) WebLLM: Qwen3 non-thinking inserts an empty `<think>\n\n</think>\n\n` block; if SFT renders it differently from inference, the model degrades silently. Expected: all runtimes render byte-identical prompts. [T6]
2. **Corpus bytes differ across FFmpeg builds** (Kaggle apt ships 6.1, local is 9): regenerated clips change hashes and checker measurements. Expected: clips come from a pinned tarball with sha256 verification; one pinned FFmpeg everywhere. [T3]
3. **Size-target reward hacking:** a blank, tiny or truncated video meets "under 2 MB". Expected: size tasks also require duration preservation and a quality floor; mutated outputs fail. [T4]
4. **Over-refusal / over-ask collapse in GRPO:** `unsupported`/`ask_user` are cheap, safe-looking actions. Expected: telemetry gate stops the run if refusal rate on supported tasks exceeds the band; the clarify term penalises it. [T18, T19, T20]
5. **Filter-made A/V offsets are unverifiable:** `adelay` leaves timestamps unchanged, so correct F11 solutions via filters fail the checker (a false negative, wasted teacher spend, not corrupted data). Expected: reference solutions use timestamp offsets (`-itsoffset`), gold specs say so, and the teacher pilot reports the F11 keep-rate. [T7, T13]

---

## Gates and owner steps (nothing here starts without the owner)

| Gate | Needs | Blocks |
|---|---|---|
| **G0a Kaggle kill-and-resume** | verifier says `"ok": true` (**satisfied 17 Nov**, D-022) | **T16+ only** (T1-T15 never wait for it) |
| **G0b/c plan and spike review** | owner reviewed the 50 dev tasks (`spike-v1`) and approved the plan: D-027 (with changes), D-028, D-029, D-030, D-031 approved 17 Nov; D-032 undecided | T1+ (done) |
| **G-terms** | owner reads and confirms DeepSeek's current terms allow training on outputs (D-010 flagged a conflicting report) and sends the **off-peak window** to put in config | T13 pilot |
| **G-clips** | owner supplies ≥10 own recordings (phone, with audio, mixed orientation) + licence statement; later writes ≈100 test-real requests | T3 real clips, T24 test-real |
| **[ASK] G1 pilot** | go-ahead to spend ≤ $0.05 on ≤ 20 train tasks | T13 |
| **[ASK] G2 bulk teacher** | go-ahead after pilot report, with the cost estimate | T14 |
| **[ASK] G3 GRPO** | go-ahead for the shuffled control (≈3 GPU-h) and then the main run (≤ 15 GPU-h cap) | T20, T21 |
| **[ASK] G4 test run** | preregistration marked FINAL + selected checkpoint + owner go-ahead; test run happens once | T22 |

**Decisions (recorded in `DECISIONS.md`; approved by the owner 17 Nov 2026 unless marked):**
- D-027 Split design: content-key hashing, held-out family *combinations* for test-compositional, held-out phrasing *styles* for test-phrasing, B0 authored from train styles only.
- D-028 M1/M3 are evaluated through merged GGUF in llama.cpp (deployment path), not HF generate.
- D-029 Corpus is distributed as a hash-verified tarball in a private HF dataset repo; the FFmpeg version question is D-024 (browser parity), which this plan builds on once the owner decides it.
- D-030 Test-run lock: a test split can be evaluated once per system+checkpoint; reruns need a logged `--supersede` reason.
- D-031 M2 (single-turn GRPO ablation) deferred to Phase 4; Phase 1 table is B0, B2, M1, M3, X1 as the exit criteria say. 1.7B is a stretch (SFT first; GRPO only if the 0.6B result and the measured 1.7B GPU-h/step justify it).

**Proposed numeric gates (to be preregistered at G0; they decide *when to continue*, not what to report):** teacher pilot continues to bulk only if kept-rate ≥ 70 % overall and cache-hit ratio ≥ 60 %; GRPO starts only if M1 dev success ≥ 60 % and invalid-action rate ≤ 5 %; minimum meaningful difference for Q2/Q3 = 5 pp on test-iid.

## Budget plan

| Item | Estimate | Basis |
|---|---|---|
| Paraphrase train tasks (+ judge) | ≤ $0.30 | measured $0.0001/task in the paraphrase check (50 tasks = $0.005) |
| Teacher pilot | ≤ $0.05 | 20 tasks × $0.00056 (X1 measured $0.028/50 at peak billing) |
| Teacher bulk | ≤ $2.30 (cap) | ≈ 3,500 tasks + failure resamples at ≤ $0.0006; real cost ≈ half if off-peak |
| X1 on four test splits | ≤ $0.70 | ≈ 1,000 tasks × $0.00056 |
| Reserve | ≥ $0.60 | |
Kaggle GPU-h (**unmeasured assumptions, [VERIFY] each**): SFT 0.6B ≈ 2 h; shuffled control ≈ 3 h; main GRPO ≤ 15 h cap (≈100 steps at ≤ 0.15 GPU-h/step after batching); 1.7B SFT stretch ≈ 6 h. Phase 0 measured 0.071 GPU-h per 16-rollout step with one-sequence-at-a-time HF generate.

## Critical path (≈10 working days if gates clear promptly; Kaggle queues add 1–3 days)

```text
G0 ─▶ T1-T5 (infra, corpus, checker) ─▶ T6 prompt freeze ─▶ T7-T10 taskgen ─▶ T11 build+leakage ─▶ T12 prereg+dev baselines
                                                                     │
        T17 lockstep rollouts (parallel track, Kaggle) ◀─────────────┤
                                                                     ▼
 G1 ─▶ T13 pilot ─▶ G2 ─▶ T14 bulk + T15 rejection ─▶ T16 SFT data+train ─▶ T16b M1 eval ─▶ T18 pass-rates ─▶ G3 ─▶ T19 control ─▶ T20 main ─▶ T21 select (dev)
                                                                                                                                 │
                           T23 CLI (parallel from T16b)   T22 export+parity  ◀────────────────────────────────────────────────┘
                                                                                     G4 ─▶ T24 test run ─▶ T25 cards + phase report
```

## File Structure

| Path | Responsibility |
|---|---|
| `packages/protocol/schemas/{task,spec}.schema.json` | add test splits, `style`, `content_key`, `quality` spec field; protocol 0.2.0 |
| `packages/protocol/prompts/system-v1.txt` | frozen short system prompt (sha256 in config) |
| `packages/protocol/conformance/*.jsonl|json` | new golden cases: quality, loudness, frames, chat template, describe-spec |
| `training/taskgen/{loader,splits,build,phrasing,phrasing_heldout,compose,special,paraphrase}.py`, `training/taskgen/families/*.py` | generator v1 |
| `training/corpus/{make_synthetic,ingest_real,hub}.py` | corpus v1, real-clip ingest, tarball push/pull |
| `training/env/{checker,quality,executor,chat_template,describe_spec}.py` | checker v1 additions, sandbox option, template, spec describer |
| `training/teacher/{generate,datacard}.py` | teacher runner, data card |
| `training/sft/{rejection,dataset,train}.py` | SFT data and trainer |
| `training/export/{merge,gguf}.py`, `eval/parity.py` | merge, GGUF, parity |
| `training/grpo/{lockstep,main_run}.py` | batched rollouts, main driver |
| `eval/{testlock,leakage,final_report}.py`, `eval/PREREGISTRATION.md` | single-shot test runner guard, leakage audit, report builder |
| `apps/cli/ffmpeg_agent_cli/` | `ffmpeg-agent` CLI |
| `reports/<date>-phase-1/` | immutable outputs |

---

## Part A: Infrastructure (no spend)

### Task 1: Protocol 0.2.0 and the split guard

**Files:**
- Modify: `packages/protocol/schemas/task.schema.json`, `packages/protocol/schemas/spec.schema.json`, `training/config.py` (`PROTOCOL_VERSION = "0.2.0"`, `TEST_SPLITS`, `SPLIT_PURPOSES`)
- Create: `training/taskgen/loader.py`
- Test: `tests/taskgen/test_loader.py`, `tests/test_protocol_schemas.py` (extend)

**Interfaces:**
- Produces: `load_tasks(split: str, purpose: Literal["train","teacher","sft","grpo","dev-eval","tune","test-eval"], *, version: str = "v1") -> list[dict]`. `SPLIT_PURPOSES` maps each purpose to the splits it may read (`train`, `teacher`, `sft`, `grpo` → `train`/`toy`; `dev-eval`, `tune` → `dev`; `test-eval` → the four `test-*` splits). Raises `SplitAccessError` otherwise.
- Task schema gains `split ∈ {train, dev, toy, test-iid, test-compositional, test-phrasing, test-real}`, optional `style: string`, `content_key: string`. Spec output gains optional `quality: {min_ssim: number|null, min_psnr_db: number|null}` (null = unconstrained). Additive, so minor bump; existing conformance and `spike-v0` tasks still validate.

- [ ] **Step 1: Write failing tests** `test_teacher_cannot_read_test_split`, `test_test_eval_cannot_read_train`, `test_tune_reads_dev_only`, `test_schema_accepts_spike_v0_and_new_splits`, `test_quality_field_nullable`.
- [ ] **Step 2: Run** `uv run pytest tests/taskgen/test_loader.py tests/test_protocol_schemas.py -v`. Expected: FAIL (module/enum missing).
- [ ] **Step 3: Implement** loader + schema edits + config. One approach: purposes are an explicit dict in config; the loader checks the file's `split` field too, so a mislabelled file fails loudly.
- [ ] **Step 4: Run** same command. Expected: PASS; also `uv run pytest -q` stays green.
- [ ] **Step 5: Commit** `feat(protocol): 0.2.0 task splits and quality spec field; split-purpose guard`.

### Task 2: Pinned FFmpeg and sandboxed rollouts

**Files:**
- Modify: `training/config.py` (`FFMPEG_PINNED_VERSION`, `ROLLOUT_RUN_TIMEOUT_S = 20`, `ROLLOUT_MAX_OUTPUT_BYTES = 50 * 2**20`), `training/env/executor.py`
- Create: `training/env/sandbox.py`, `training/corpus/ffmpeg_pin.sh`
- Test: `tests/env/test_sandbox.py`

**Interfaces:**
- Produces: `sandbox_prefix(require: bool) -> list[str]`: `["bwrap", "--unshare-net", "--ro-bind", …]` when bubblewrap works, `[]` when it is unavailable and `require=False`, raises `SandboxUnavailable` when `require=True`. `execute(..., sandbox: bool = False)` prepends it; rollouts use `ROLLOUT_RUN_TIMEOUT_S`.

- [ ] **Step 1: Write failing tests** `test_prefix_fails_closed_when_required_and_missing` (monkeypatch `shutil.which`), `test_prefix_empty_when_optional`, `test_network_protocol_still_rejected_by_validator`, `test_rollout_timeout_kills_hung_ffmpeg` (a `-f lavfi` infinite source with the rollout timeout; asserts a timeout result, no orphan process).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** `ffmpeg_pin.sh` downloads one pinned static build (URL + sha256 in the script header), used locally and on Kaggle; manifest records `ffmpeg -version`. Where bwrap is unusable on Kaggle (check once in the notebook), the run documents "validator-only isolation" as a limitation; do not silently fall back when `require=True`.
- [ ] **Step 4: Run** → PASS. Run the pinned build against the existing conformance suite (`uv run pytest tests/conformance -q`) and note any hash differences.
- [ ] **Step 5: Commit** `feat(env): optional bubblewrap sandbox, rollout timeouts, pinned static FFmpeg`.

### Task 3: Corpus v1 and distribution

**Files:**
- Modify: `training/corpus/make_synthetic.py`
- Create: `training/corpus/hub.py`, `training/corpus/ingest_real.py`
- Test: `tests/corpus/test_corpus_v1.py`, `tests/corpus/test_hub.py`

**Interfaces:**
- Produces: manifest record gains `known_offset_ms: float | None`, `tags: list[str]` (e.g. `["vfr","portrait","rot270","mono","prores"]`). `push_corpus(dir, repo_id, api=None)` / `pull_corpus(repo_id, dest, api=None) -> dict[str, Path]` (tarball + manifest; verifies every sha256, refuses mismatches). `ingest_real(path, licence: str, source: str, consent: bool) -> ClipRecord` refuses an empty licence.
- Coverage added over Phase 0's 12 clips (ARCH §7.1): VFR, rotation 270/180 metadata, 4:3, ProRes-lite, MKV, mono and 44.1 kHz audio, noisy/quiet audio, clips with a baked known A/V offset (±200/±500 ms), 2–20 s durations. Real clips are added through `ingest_real` (see Review Focus 2: tarball, not regeneration).

- [ ] **Step 1: Write failing tests** `test_every_recipe_probes_as_tagged`, `test_known_offset_clip_measures_within_tolerance` (first-packet method), `test_manifest_hashes_verified_on_pull`, `test_pull_rejects_tampered_clip`, `test_ingest_real_requires_licence`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** recipes (`-itsoffset` for baked offsets), `hub.py` (HfApi upload of one `corpus-v1.tar.zst` + `manifest.json`, private dataset repo `JustJoyful/ffmpeg-agent-corpus`), `ingest_real.py` (copies, probes, records licence/source/consent).
- [ ] **Step 4: Run** → PASS; then `push_corpus` the synthetic set (real clips join at G-clips).
- [ ] **Step 5: Commit** `feat(corpus): corpus v1 recipes, tagged manifest, hash-verified Hub distribution, real-clip ingest`.

### Task 4: Checker v1 completion and conformance cases

**Files:**
- Modify: `training/env/checker.py`, `training/config.py` (`SSIM_FLOOR_DEFAULT`, `PSNR_FLOOR_DB_DEFAULT`, `QUALITY_SAMPLE_FRAMES`)
- Create: `training/env/quality.py`, `packages/protocol/conformance/{checker-quality,checker-loudness,checker-frames}.jsonl`
- Test: `tests/env/test_checker_v1.py`, `tests/conformance/test_conformance_python.py` (extend)

**Interfaces:**
- Produces: `measure_quality(reference: Path, candidate: Path, sample_frames: int) -> {"ssim": float, "psnr_db": float}` (candidate scaled to reference size; FFmpeg `ssim`/`psnr` filters on a fixed frame subset). `check(...)` reports `quality.min_ssim`/`quality.min_psnr_db` checks when set, and **size-target tasks (`size_max_bytes` set) always also check duration preservation** (field `time` derived from input if not set) and a default quality floor, per ARCH §7.4 guards.
- Conformance cases: each line `{"name", "recipe", "spec", "expect": {"passed": bool, "fields": {...}}}` so the Phase 2 TS checker reuses them.

- [ ] **Step 1: Write failing tests** `test_blank_video_under_size_target_fails_quality`, `test_truncated_output_under_size_target_fails_duration`, `test_good_compression_passes_with_floor`, `test_loudness_within_2lu_passes_and_3lu_fails`, `test_frame_count_off_by_two_fails`, `test_silent_audio_fails_loudness`. Each uses a mutated output made by ffmpeg from the corpus.
- [ ] **Step 2: Run** `uv run pytest tests/env/test_checker_v1.py -v` → FAIL.
- [ ] **Step 3: Implement** `quality.py` and the checker additions. Do not loosen existing tolerances (RULES §4.1). Record the checker version string `checker-v1.1` in `check()` output measurements and in every report manifest.
- [ ] **Step 4: Run** full suite → PASS; re-grade the Phase 0 dev tasks with B0 (`uv run python -m eval.run_baseline --system B0 …` on `spike-v0` into a fresh dir). The score may change under checker v1.1 (the quality floor and duration guard are new): **report each changed task and explain why**, do not expect 46/50 unchanged and do not loosen the checker to restore it.
- [ ] **Step 5: Commit** `feat(checker): v1.1 quality floor and duration guard for size targets, loudness/frame golden cases`.

### Task 5: Dev-task review and `spike-v1` (owner gate G0b)

**Files:** Modify `data/tasks/dev/spike-v1.jsonl` (new), `eval/PREREGISTRATION.md` (post-hoc note), `PHASES.md`.

- [ ] **Step 1:** Print the 50 tasks and gold specs as a table for the owner (`uv run python -m eval.show_tasks data/tasks/dev/spike-v0.jsonl`, a 20-line helper).
- [ ] **Step 2 (owner):** accept as is, or list edits. Edits create `spike-v1`; results on v1 are reported separately and never merged with v0 numbers.
- [ ] **Step 3:** Record the outcome in `PHASES.md` follow-ups. **No Phase 0 file is edited.**
- [ ] **Step 4: Commit** `docs(phase0): owner review of spike tasks recorded`.

---

## Part B: Frozen format

### Task 6: Prompt v1 and chat-template parity

**Files:**
- Create: `packages/protocol/prompts/system-v1.txt`, `training/env/chat_template.py`, `packages/protocol/conformance/chat-template.json`
- Modify: `training/config.py` (`SYSTEM_PROMPT_V1_SHA256`, `PROMPT_VERSION = "v1"`), `training/env/loop.py` (default prompt = v1)
- Test: `tests/env/test_chat_template.py`

**Interfaces:**
- Produces: `render(messages: list[dict], *, add_generation_prompt: bool, tokenizer) -> str` implementing Qwen3 non-thinking (`<think>\n\n</think>\n\n` after the assistant header, none in history turns); `tokenize_with_mask(messages, tokenizer) -> (input_ids: list[int], assistant_mask: list[int])` where mask = 1 only on assistant action tokens and their `<|im_end|>`.
- Prompt v1 is short and example-free in the style of `system-v0-small.txt` (Phase 0: copyable examples leak into small-model outputs); the format knowledge comes from SFT. Frozen by hash; changing it later invalidates teacher data (cache prefix) and needs a new `PROMPT_VERSION`.

- [ ] **Step 1: Write failing tests** `test_prompt_hash_pinned`, `test_render_matches_golden_strings` (golden file with 4 conversations incl. an observation turn), `test_mask_covers_only_assistant_tokens`, `test_template_matches_llama_server_apply_template` (skips if no server on `LLAMA_SERVER_URL`; compares the HF render to `/apply-template`).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Use the tokenizer's own template as the reference; our renderer exists to produce the mask and to pin goldens, and the test proves they agree (Review Focus 1).
- [ ] **Step 4: Run** → PASS (run the llama.cpp parity test locally with the Qwen3-0.6B GGUF server up).
- [ ] **Step 5: Commit** `feat(protocol): system prompt v1 frozen by hash, Qwen3 non-thinking template with assistant-token mask`.

---

## Part C: Task generator v1

### Task 7: Family templates with generate-and-verify

**Files:**
- Create: `training/taskgen/families/{time,merge,convert,scale,extract,audio}.py`, `training/taskgen/families/__init__.py`, `training/taskgen/verify.py`
- Test: `tests/taskgen/test_families.py`

**Interfaces:**
- Produces: `@family("F1")` registry; `FamilyTemplate.draft(rng: random.Random, clips: ClipIndex) -> TaskDraft` where `TaskDraft = {families, inputs, slots, gold_spec, reference_runs, difficulty}` and `slots` are the values a phrasing template fills (e.g. `{"start_s": 3}`). `verify_draft(draft, corpus, jobs_root) -> VerifyResult(ok: bool, reason: str|None)` runs `reference_runs` through validator → executor → checker against `gold_spec`.
- Rules: parameters sampled from clip probes so tasks are feasible (F6 size targets ≥ a feasibility floor computed from a probe encode; F11 uses clips with `known_offset_ms` and gold `offset_ms` of the correction; reference F11 solution uses `-itsoffset` (Review Focus 5); F5 prefers metadata rotation when lossless is requested; F3 only on HEVC/MOV/WebM/AVI inputs). Reference runs use stream copy wherever a lossless solution exists, which gives the "unnecessary re-encode" metric its ground truth.

- [ ] **Step 1: Write failing tests** `test_each_family_registered_f1_to_f12`, `test_every_family_draft_verifies_over_50_seeds` (parametrised; assert 0 failures or list them), `test_infeasible_size_target_never_emitted`, `test_f11_reference_uses_itsoffset_and_passes_checker`, `test_lossless_reference_is_stream_copy`.
- [ ] **Step 2: Run** `uv run pytest tests/taskgen/test_families.py -v` → FAIL.
- [ ] **Step 3: Implement** one module per group; share slot samplers in `families/__init__.py` (no copy-paste per family).
- [ ] **Step 4: Run** → PASS (≈ minutes: real FFmpeg runs; mark with `@pytest.mark.slow` and keep a small default subset in CI).
- [ ] **Step 5: Commit** `feat(taskgen): F1-F12 templates with executed-reference verification`.

### Task 8: Phrasing styles (train styles vs held-out styles)

**Files:**
- Create: `training/taskgen/phrasing.py`, `training/taskgen/phrasing_heldout.py`
- Modify: `training/config.py` (`TRAIN_STYLES`, `HELDOUT_STYLES`)
- Test: `tests/taskgen/test_phrasing.py`

**Interfaces:**
- Produces: `render_request(family: str, slots: dict, style: str, rng: random.Random) -> str`. Styles (proposal): train = `terse`, `polite`, `verbose`, `symptom` ("won't play on my TV"), `casual_typos`; held-out = `context_first` (a situation first, then the problem, e.g. "for my viva tomorrow, ppt won't play this"; owner-approved replacement for `technical`) and `indirect` (a goal first, then the request). Each family has ≥ 4 templates per style. Held-out templates live **only** in `phrasing_heldout.py`, imported by exactly one module (`splits.build`); the B0 author never opens it (D-027 process control).

- [ ] **Step 1: Write failing tests** `test_all_slots_appear_in_request` (digits/units preserved, the same digit rule as `eval/paraphrase.py`), `test_every_family_has_templates_for_every_style`, `test_heldout_templates_not_importable_outside_build` (AST check over the repo), `test_no_template_overlap_between_train_and_heldout`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(taskgen): phrasing styles with held-out styles isolated for test-phrasing`.

### Task 9: Compositions, ambiguity and unsupported tasks

**Files:** Create `training/taskgen/compose.py`, `training/taskgen/special.py`; Test `tests/taskgen/test_compose.py`, `tests/taskgen/test_special.py`.

**Interfaces:**
- Produces: `COMPATIBLE: dict[frozenset[str], bool]` in config-driven form (e.g. F9-remove-audio ∧ F10 incompatible; F7 ∧ F8 incompatible); `compose(drafts: list[TaskDraft]) -> TaskDraft | None` merges output specs (conflict → `None`) and builds `reference_runs` (one command when filters chain, otherwise ≤ `MAX_RUNS_PER_JOB`); `make_ambiguous(rng) -> task` (gold_spec null, `clarification` = answer text, 3+ ambiguity kinds: missing duration, missing target size, unspecified "fix"); `make_unsupported(rng) -> task` (≥ 8 categories: object removal, subtitles/transcription, colour grading, upscaling, background removal, watermark removal, voice change, translation; `nearest_supported` where one exists). Target mix (config): ambiguous ≈ 8 %, unsupported ≈ 8 %, difficulty 1 : 2 : 3 : 4 families ≈ 55 : 30 : 12 : 3 %.

- [ ] **Step 1: Write failing tests** `test_incompatible_pair_returns_none`, `test_composed_reference_passes_checker_for_20_random_pairs`, `test_triple_composition_difficulty_is_3`, `test_ambiguous_task_has_clarification_and_null_gold`, `test_unsupported_task_flags`, `test_ask_user_answer_used_by_loop` (scripted policy asks once, loop injects the clarification, then the task resolves against the resolved gold spec; extend `loop.run_episode` if it does not yet inject it).
- [ ] **Step 2–4: Run/implement/run.** **Step 5: Commit** `feat(taskgen): compositions of 2-4 families, ambiguous and unsupported tasks`.

### Task 10: Split assignment, build CLI, manifest

**Files:** Create `training/taskgen/splits.py`, `training/taskgen/build.py`, `data/tasks/MANIFEST.json`, `data/tasks/{train,dev,test-iid,test-compositional,test-phrasing}/v1.jsonl`; Modify `training/config.py` (`SPLIT_TARGETS`, `HELDOUT_COMBOS`, `TASKGEN_SEED`, `TASKGEN_VERSION = "1.0"`); Test `tests/taskgen/test_build.py`.

**Interfaces:**
- Produces: `content_key(draft) -> str` = sha256 of canonical `(families, inputs, gold_spec)`; paraphrases and styles of one draft share the key. `assign_split(draft, style) -> str`: if the style is held-out → `test-phrasing` pool; elif its family combination ∈ `HELDOUT_COMBOS` → `test-compositional`; else `sha256(content_key + seed) mod 100` buckets into train/dev/test-iid (≈ 70/5/25 of the non-heldout stream, tuned to hit `SPLIT_TARGETS`). CLI: `uv run python -m training.taskgen.build --out data/tasks --seed N` writes JSONL and `MANIFEST.json` (generator version, seed, per-split count, sha256, family and difficulty distribution, drop log from `verify_draft`).

- [ ] **Step 1: Write failing tests** `test_build_is_deterministic` (twice → identical sha256), `test_splits_disjoint_by_content_key`, `test_compositional_combos_absent_from_train`, `test_heldout_styles_absent_from_train_and_dev`, `test_manifest_hashes_match_files`, `test_family_share_cap` (no family > 20 % of train), `test_test_splits_are_not_readable_for_training_purposes` (uses T1 guard).
- [ ] **Step 2–4.** **Step 5: Commit** `data(taskgen): v1 train/dev/test splits, hash-pinned manifest` (JSONL + manifest committed; clips are not).

### Task 11: Train paraphrases and the leakage audit

**Files:** Create `training/taskgen/paraphrase.py`, `eval/leakage.py`; Test `tests/taskgen/test_paraphrase_train.py`, `tests/eval/test_leakage.py`.

**Interfaces:**
- Consumes: `eval.paraphrase.paraphrase_tasks(tasks, write, judge)` (digits rule + judge); `BudgetGuard`.
- Produces: `paraphrase_train(split_file, out, budget_usd, n_per_task=1)` that only accepts `purpose="train"` tasks via the T1 loader; adds paraphrases as new train tasks sharing the source `content_key`. `leakage_report(train_requests, test_requests, n=4) -> {"max_jaccard": float, "pairs_over_threshold": list}`; CI test fails if any train/teacher request shares ≥ `LEAKAGE_JACCARD_MAX` of its 4-grams with any test request.

- [ ] **Step 1: Write failing tests** `test_paraphrase_refuses_test_split`, `test_paraphrase_keeps_content_key`, `test_leakage_flags_near_duplicate`, `test_leakage_clean_on_generated_splits`.
- [ ] **Step 2–4.** Dry-run the paraphrase first (`--dry-run` prints cost estimate), then **[ASK]** the owner for ≤ $0.30 before the real run (this spends DeepSeek budget). **Step 5: Commit** `feat(taskgen): budget-guarded train paraphrases; n-gram leakage audit`.

### Task 12: Preregistration, test-run lock and dev baselines

**Files:** Modify `eval/PREREGISTRATION.md` (new Phase 1 section, Status DRAFT until G4), `eval/run_baseline.py`; Create `eval/testlock.py`, `eval/b0_regex_v2.py`; Test `tests/eval/test_testlock.py`.

**Interfaces:**
- Produces: `acquire_test_run(system: str, checkpoint: str, split: str, ledger: Path, supersede_reason: str | None = None) -> None` appends to `reports/TEST_RUNS.jsonl` and raises `TestAlreadyRun` on a repeat; `run_baseline` calls it for `test-*` splits and refuses unless PREREGISTRATION contains `Phase 1 status: FINAL`. B0 v2 is written **from train-style phrase banks only** (never `phrasing_heldout.py`), then frozen with a git tag and file hash (same procedure as `FREEZE.md`) before any test split is generated or run.
- Preregistration content: the comparison family (Q2 M1 vs B2; Q3 M3 vs M1; Q4 M3 vs X1; Q5 M3 per test split; Q7 M3 vs B0 per family), Holm over those, minimum meaningful difference 5 pp, the single-seed disclosure, stopping rules for GRPO, the numeric continue-gates from this plan, and "B0 is hand-written from train styles; held-out styles were not read by its author".

- [ ] **Step 1: Write failing tests** `test_second_test_run_refused`, `test_supersede_requires_reason_and_is_logged`, `test_test_run_refused_unless_prereg_final`, `test_dev_run_unaffected`.
- [ ] **Step 2–4.** Then run **free dev baselines** with prompt v1 on `dev/v1.jsonl`: B0 v2, B2 Qwen3-0.6B and 1.7B (llama-server, capped systemd unit as in Phase 0), and X1 on dev ≤ $0.05 after owner OK.
- [ ] **Step 5: Commit** `eval(phase1): preregistration draft, test-run lock, B0 v2 frozen, dev baselines on v1`.

---

## Part D: Teacher and SFT data

### Task 13: Teacher runner, pilot report [ASK G1 / G-terms]

**Files:** Create `training/teacher/generate.py`, `training/teacher/datacard.py`; Modify `training/config.py` (`DEEPSEEK_OFFPEAK_UTC`, `TEACHER_MODEL_TERMS_URL`, `TEACHER_TERMS_SNAPSHOT_SHA256`); Test `tests/teacher/test_generate.py`.

**Interfaces:**
- Consumes: `load_tasks("train", purpose="teacher")`, `policy_from_config`, `run_episode`, `score`, `BudgetGuard`.
- Produces: `generate(tasks, out_dir, guard, *, k: int = 1, resume: bool = True, offpeak_only: bool = False) -> GenSummary(kept, attempted, cost_usd, cache_hit_ratio, by_family: dict)`; writes `trajectories.jsonl` (full transcript: system, messages, actions, check results, usage) and **only passing** episodes into `kept.jsonl`; skips task ids already present (resumable). `datacard.build(out_dir) -> Path` (model id, date, terms URL + snapshot hash, prices, seeds, family distribution, cost).
- The teacher prompt contains request + probes + system prompt v1 **only**: never the gold spec or reference runs (test asserts it).

- [ ] **Step 1: Write failing tests** `test_teacher_messages_never_contain_gold_spec_or_reference` (scan serialized messages against both), `test_only_passing_trajectories_kept`, `test_resume_skips_done_tasks`, `test_budget_exceeded_stops_cleanly_and_records_partial`, `test_offpeak_gate_refuses_peak_when_required` (fake clock), `test_datacard_has_terms_snapshot`.
- [ ] **Step 2–4.** **Step 5: Commit** `feat(teacher): resumable budget-guarded trajectory generator and data card`.
- [ ] **Step 6 [ASK G1]:** pilot on ≤ 20 train tasks (≤ $0.05, ≥ 1 task per family incl. F11, ambiguous, unsupported). Write `reports/<date>-teacher-pilot/` with kept-rate by family, cost/task, cache-hit ratio, 10 hand-read kept trajectories. **Stop and report; the owner decides G2.**

### Task 14: Bulk teacher data [ASK G2]

**Files:** Create `reports/<date>-teacher-bulk/` (manifest, data card), `data/sft/teacher-v1/` (gitignored large files; manifest tracked).

- [ ] **Step 1:** Re-check DeepSeek pricing and off-peak window on the official page; update `config.py` prices/date if changed (they changed several times in 2026).
- [ ] **Step 2:** Run `generate` over the train tasks in chunks of 500 via `--budget-usd` per chunk, off-peak only, concurrency ≤ `DEEPSEEK_CONCURRENCY_LIMIT`; after each chunk print kept-rate and running cost; auto-stop at the cap in the plan's budget table.
- [ ] **Step 3:** Failed tasks get one resample (`k=2`) at temperature 0.7 only if budget allows; record which tasks never pass (these feed the taxonomy, not the SFT set).
- [ ] **Step 4: Verify:** `uv run python -m training.teacher.datacard build <dir>` produces the card; spent total printed; ledger shows no unsettled reservations.
- [ ] **Step 5: Commit** `data(teacher): bulk teacher trajectories manifest and data card` (manifest + card only; trajectories upload to the private HF dataset repo `JustJoyful/ffmpeg-agent-sft`).

### Task 15: Rejection sampling from the base model (free)

**Files:** Create `training/sft/rejection.py`; Test `tests/sft/test_rejection.py`.

**Interfaces:** `rejection_sample(tasks, policy, n: int = 8, temperature: float = 0.8, max_difficulty: int = 1) -> list[Episode]` keeps passing episodes of difficulty-1 tasks only; capped in the final mix (T16). Why capped: base-model successes are easy, low-information and in the base model's own style; they regularise format but must not dominate.

- [ ] **Step 1: Write failing tests** `test_only_passing_kept`, `test_difficulty_filter`, `test_dedupes_identical_trajectories`. **Step 2–4.** Run against llama-server Qwen3-1.7B with prompt v1 on easy train tasks (free, local; capped systemd unit). **Step 5: Commit** `feat(sft): rejection sampling of easy tasks from base Qwen3`.

### Task 16: SFT dataset and trainer, then M1

**Files:**
- Create: `training/sft/dataset.py`, `training/sft/train.py`, `training/export/merge.py`, `training/export/gguf.py`, `eval/configs/m1-0.6b-q8.toml`
- Modify: `training/grpo/kaggle_kernel.py` (generalise: `--entry`, `--args`), `training/config.py` (`SFT_*` hyperparameters, `MIX_*` caps)
- Test: `tests/sft/test_dataset.py`, `tests/sft/test_train_smoke.py` (skips without torch)

**Interfaces:**
- Produces: `build_examples(trajectories: list[dict], tokenizer, *, max_len: int) -> list[{"input_ids": list[int], "labels": list[int]}]` using `tokenize_with_mask` (labels = −100 outside assistant tokens); `mix(teacher, rejection, *, per_family_cap: float, rejection_share_max: float, seed) -> list[dict]`; `train.py --model Qwen/Qwen3-0.6B --data <hf-or-path> --epochs 3 --hub-repo … --ckpt-dir …` (LoRA r16 α32 all-linear, lr 1e-4 as a starting point to tune on a held-out **train-content** validation slice, fp16 via `precision_plan`, `SyncCallback` for off-box checkpoints, resume verified by `verify_resume`); `merge_lora(base, adapter, out_dir)`; `to_gguf(model_dir, out, quant: Literal["q8_0","q4_k_m"])` via llama.cpp `convert_hf_to_gguf.py` + `llama-quantize` (pinned b12032).

- [ ] **Step 1: Write failing tests** `test_labels_masked_outside_assistant`, `test_im_end_included_in_loss`, `test_examples_longer_than_max_len_dropped_and_counted`, `test_mix_caps_family_share_and_rejection_share`, `test_validation_slice_uses_train_content_keys_only` (no dev/test), `test_smoke_two_steps_cpu` (torch only).
- [ ] **Step 2–4.** Run SFT on Kaggle via `kaggle_kernel` (kill-and-resume path already proven at G0): ≈ 2 h. Pull the adapter, merge, convert to GGUF Q8_0, serve with `llama-server`, run `eval.run_baseline` on `dev/v1.jsonl`.
- [ ] **Step 5: Commit** `feat(sft): masked multi-turn LoRA SFT, merge and GGUF export, M1 dev eval`; report to `reports/<date>-m1-dev/`.
- [ ] **Step 6 (decision gate):** M1 dev success ≥ 60 % and invalid-action rate ≤ 5 % (preregistered): continue. Otherwise stop and read failure taxonomy (`eval/taxonomy.py`) before touching GRPO. Iterate data (not the checker) and record each iteration as `M1-run-N`; the selected data recipe is chosen on dev only.
- [ ] **Step 7 (stretch):** repeat for Qwen3-1.7B if the T4 budget allows (≈ 6 h).

---

## Part E: GRPO

### Task 17: Lockstep batched rollouts (parallel track, starts after T10)

**Files:** Create `training/grpo/lockstep.py`; Modify `training/grpo/rollout.py` (`make_rollout_func(..., batch_generate=...)`); Test `tests/grpo/test_lockstep.py`.

**Interfaces:**
- Produces: `run_episodes_lockstep(tasks: list[dict], generate_batch: Callable[[list[list[int]], int], list[tuple[list[int], list[float]]]], *, corpus, jobs_root, max_new_tokens, max_runs, workers: int = 4) -> list[Episode+trajectory]`. All episodes advance one turn per round: batch the pending prompts into **one** `generate` call, then execute that round's FFmpeg runs in a thread pool. Per-episode token streams and `env_mask` are unchanged (observations masked) so `rollout_func` returns the same structure as in Phase 0. Rationale: the Phase 0 generator decodes one sequence at a time (0.071 GPU-h per 16 rollouts is an upper bound); GRPO groups are naturally batchable.

- [ ] **Step 1: Write failing tests** `test_lockstep_matches_sequential_for_deterministic_fake_generator` (same actions, same rewards, same masks), `test_finished_episodes_leave_the_batch`, `test_a_run_timeout_does_not_stall_other_episodes`, `test_batch_size_one_equals_toy_path`.
- [ ] **Step 2–4.** Measure on Kaggle (notebook cell → `reports/<date>-lockstep-throughput/`): GPU-h per 64 rollouts, sequential vs lockstep, plus the 1.7B figure from the pending Phase 0 cell. Timebox: if HF batched generate does not reach ≤ 0.15 GPU-h per 64-rollout step, spend at most one day on vLLM-colocate [VERIFY T4/fp16]; otherwise reduce group size and report the limit.
- [ ] **Step 5: Commit** `perf(grpo): lockstep batched multi-turn rollouts`.

### Task 18: Pass-rate table from M1 and reward fixtures

**Files:** Modify `training/grpo/taskfilter.py` (policy from a llama-server config), `training/grpo/telemetry.py` (size-target and refusal guards); Create `tests/grpo/test_reward_guards.py`.

- [ ] **Step 1: Write failing tests** `test_blank_small_output_gets_no_pass_reward`, `test_all_refuse_policy_reward_below_do_the_task`, `test_ask_on_supported_task_penalised`, `test_telemetry_flags_refusal_rate_over_band` (config `REFUSAL_RATE_BAND`).
- [ ] **Step 2–4.** Compute `pass_rates.json` on **train tasks only** with the M1 GGUF (K = 8, local), upload to the HF checkpoint repo so Kaggle runs consume it. Report in-band share; if < 30 % of train tasks are in band, widen the generator's difficulty mix rather than the band.
- [ ] **Step 5: Commit** `feat(grpo): M1 pass-rate table, reward guards for size and refusal collapse`.

### Task 19: Shuffled-reward control [ASK G3]

**Files:** Create `training/grpo/main_run.py` (generalises `toy_spike.py`: `--init <merged SFT model>`, `--reward v1`, `--task-filter`, `--hub-repo`, `--crash-after` kept, lockstep rollouts, telemetry gates), `reports/<date>-grpo-control/`; Test `tests/grpo/test_main_run_args.py`.

- [ ] **Step 1: Write failing tests** `test_main_run_refuses_test_splits`, `test_main_run_requires_hub_repo_for_real_runs`, `test_gate_stops_run_on_refusal_band_violation` (fake telemetry).
- [ ] **Step 2–4.** Run 30 steps with `--shuffle-rewards` (≈ 3 GPU-h, needs G3). Pass criterion (preregistered): dev success after the control is not above M1 beyond the 95 % interval and no collapse in format validity; if it improves, the pipeline leaks signal; stop and debug.
- [ ] **Step 5: Commit** `feat(grpo): main-run driver with telemetry gates; shuffled-reward control result`.

### Task 20: Main GRPO run [ASK G3]

**Files:** `reports/<date>-grpo-main/` (telemetry, curves, manifest with seed, git commit, GPU-h).

- [ ] **Step 1:** Launch via `kaggle_kernel` (checkpoint every 10 steps to the Hub; D-022), group size 8, 8 prompts per step, β = 0 as in the spike (record this choice and why: no reference model on a 16 GB T4), cap 15 GPU-h, stop rules from the preregistration (no-signal share > 60 % for 10 steps, refusal-rate violation, invalid-action rate rising, spot-check exploit).
- [ ] **Step 2:** Every 10 steps the driver dumps top-reward transcripts (`TELEMETRY_SPOTCHECK_*`); a human reads at least three per dump and notes exploits in `spotcheck-notes.md`. An exploit → fix reward in a new commit and restart from the last clean checkpoint, documenting the discontinuity.
- [ ] **Step 3:** If a session dies, resume with `--resume`; confirm `verify_resume` output in the report.
- [ ] **Step 4: Commit** `eval(grpo): main run telemetry and spot-check notes`. Null results are results: if reward does not rise beyond noise, report reward variance and saturation step.

### Task 21: Checkpoint selection on dev

**Files:** Create `eval/select_checkpoint.py`; Test `tests/eval/test_select_checkpoint.py`.

- [ ] **Step 1: Write failing tests** `test_selection_reads_dev_only`, `test_selection_rule_is_deterministic_and_prefers_earlier_on_ties`.
- [ ] **Step 2–4.** Merge + GGUF-Q8 the 3–4 candidate checkpoints (e.g. steps 30/60/90 and last), run each on `dev/v1.jsonl` (≈300 tasks, local, free). Rule (preregistered): highest dev success; ties → fewer runs/task → earlier step. Write `selected.json` (checkpoint, dev numbers, CIs).
- [ ] **Step 5: Commit** `eval(grpo): dev-only checkpoint selection`.

---

## Part F: Export, test run, CLI, release

### Task 22: Export and parity eval

**Files:** Create `eval/parity.py`; Test `tests/eval/test_parity.py`; reports `reports/<date>-parity/`.

**Interfaces:** `parity(results_a: dict[str,bool], results_b: dict[str,bool]) -> {"agreement": float, "acc_a": …, "acc_b": …, "mcnemar_p": float, "paired_diff_ci": (d, lo, hi)}`.

- [ ] **Step 1: Write failing tests** `test_parity_identical_results_agreement_one`, `test_parity_counts_discordant_pairs`. **Step 2–4.** Export the selected M3 (and M1) as fp16 (HF/`transformers`, small dev subset), GGUF Q8_0 and Q4_K_M; run each on the same 100 dev tasks. Report the quantization cost with CIs; pick the shipped native format from the numbers, not by assumption (MLC q4f16_1 parity is Phase 2). **Step 5: Commit** `eval(export): GGUF Q8/Q4 parity on dev`.

### Task 23: `ffmpeg-agent` CLI (parallel from the M1 gate)

**Files:** Create `apps/cli/ffmpeg_agent_cli/{__main__,agent,server,describe}.py`, `apps/cli/pyproject.toml` (entry point `ffmpeg-agent`), `training/env/describe_spec.py`, `packages/protocol/conformance/describe-spec.jsonl`; Test `tests/cli/test_cli.py`.

**Interfaces:**
- Produces: `describe_spec(spec: dict) -> str` (plain-language lines, one per set field; null fields omitted; the same golden cases the Phase 2 TS UI must reproduce). `ffmpeg-agent "<request>" file.mp4 [--model PATH|HF-ID] [--yes] [--out DIR]`: probe → model emits spec → CLI prints `describe_spec` and asks to confirm (`--yes` skips; this is the **user-confirmed spec** that the checker uses) → run loop (≤ 4 runs) → check → prints output path and the check summary; `ask_user` prompts on stdin; `unsupported` prints the reason. A `LlamaServer` context manager starts `llama-server` (arg list, `127.0.0.1`, random free port, pinned binary path from env/config), waits for `/health`, always terminates it. Outputs never overwrite inputs; paths stay harness-owned.

- [ ] **Step 1: Write failing tests** `test_describe_spec_golden_cases`, `test_cli_runs_scripted_policy_end_to_end` (policy fake, real FFmpeg, no model), `test_cli_aborts_when_user_rejects_spec_and_runs_nothing`, `test_cli_never_overwrites_input`, `test_server_binds_loopback_only`, `test_cli_reports_failed_check_honestly` (RULES §8.1: never claims success when the check failed).
- [ ] **Step 2–4.** Then manual proof on the owner's machine with the selected GGUF: 3 chores (trim, vertical 9:16, extract audio) recorded in `reports/<date>-cli-demo.md`.
- [ ] **Step 5: Commit** `feat(cli): ffmpeg-agent command with spec confirmation, llama.cpp supervisor, honest check reporting`.

### Task 24: The single test run [ASK G4]

**Files:** Create `eval/final_report.py`, `reports/<date>-phase-1/` (`summary.md`, `results.json`, `by_family.csv`, `telemetry/`, `manifest.json`); Modify `eval/PREREGISTRATION.md` (Status FINAL, dated); Test `tests/eval/test_final_report.py`.

**Interfaces:** `final_report(run_dirs: dict[str, dict[str, Path]]) -> Path` builds the EVALUATION §7 table (rows B0, B2, M1, M3, X1; columns test-iid, test-comp, test-phrasing, test-real, runs/task, re-encode↓, cost/task) with Wilson CIs, paired bootstrap differences for the preregistered comparisons with **Holm-adjusted** intervals/p-values, by-family and by-difficulty tables, failure taxonomy, and refuses to run if any system/split pair lacks a `TEST_RUNS.jsonl` entry or if a denominator differs between systems.

- [ ] **Step 1: Write failing tests** `test_holm_adjusts_in_declared_order`, `test_report_refuses_mismatched_denominators`, `test_report_includes_failed_and_timed_out_runs`, `test_single_seed_disclosure_present`.
- [ ] **Step 2 (owner check before running):** PREREGISTRATION is FINAL, `selected.json` exists, B0 v2 hash matches its freeze, ledger shows ≥ $0.70 headroom for X1. **[ASK G4].**
- [ ] **Step 3:** Run once per system × split through `eval.run_baseline` (test lock records each), X1 within its cap, B2/M1/M3 local GGUF Q8 (free).
- [ ] **Step 4:** Sanity controls (EVALUATION §6): leakage audit result, checker mutation self-test, **50 random passed M3 outputs** inspected by eye (`eval/spotcheck.py` samples and writes a review sheet; the owner or Claude records findings honestly, including blind spots).
- [ ] **Step 5: Commit** `eval(phase1): single preregistered test run, results table with CIs and Holm-adjusted comparisons`.

### Task 25: Cards, Hugging Face release, phase report

**Files:** Create `reports/<date>-phase-1/summary.md` (headline table + honest limitations), HF model repo `JustJoyful/ffmpeg-agent-0.6b` (GGUF Q8/Q4 + merged weights), model card, dataset repos (tasks + teacher trajectories with data card); Modify `PHASES.md` (Phase 1 ✅, Phase 2 ⏳), `DECISIONS.md` (D-027…D-031 + results decision), `README.md` limitations, `CLAUDE.md` (current state, new commands).

- [ ] **Step 1: Write failing test** `tests/test_cards.py::test_model_card_has_required_sections` (base model, data sources, teacher + terms snapshot, recipe, eval table with CIs, limitations, licence; RULES §7).
- [ ] **Step 2:** Licence audit script `eval/licences.py` over corpus manifest + datasets + models; fails on any unrecorded licence. Qwen3 (Apache-2.0), project GPL-3.0 (D-016), weights licence compatible; synthetic clips CC0; real clips per their records; DeepSeek terms snapshot attached.
- [ ] **Step 3:** Upload (private first; flip public only on the owner's say-so), then the honest summary: single seed, small test-real, synthetic-heavy corpus, B0 author-fit caveat, checker blind spots (filter-made offsets), quantization cost, X1 teacher/eval overlap disclosure (teacher and X1 are the same model family).
- [ ] **Step 4: Commit** `docs(phase1): model/data cards, release, phase report`; update CLAUDE.md "Current state".

---

## Self-review

- **Spec coverage:** PHASES Phase 1 tasks → generator T7–T11; corpus T3; checker T4; conformance T4/T6/T23; teacher T13–T14; rejection T15; SFT T16; GRPO env + run + telemetry T17–T21; eval single test run T12/T24; GGUF + CLI + parity T22–T23; cards T25. Exit criteria: table with CIs (T24), model on HF + CLI (T23/T25), honest limitations (T25). Cross-cutting rules: budget (T11/T13/T14, budget table), checkpoint/resume (T16/T20), contamination (T1/T10/T11/T24), reward guards (T4/T18), shuffled control (T19), human spot-check (T20/T24), preregistration (T12/T24). EVALUATION §6 sanity controls all mapped.
- **Not in Phase 1 (noted, not done):** MLC export and in-browser parity (Phase 2), TS checker (Phase 2, cases ready), M2 ablation and multi-seed (Phase 4), VMAF (eval-only, Phase 4).
- **Type consistency:** `load_tasks(split, purpose)` (T1) is the only task reader in T11, T13, T16, T18, T19, T21; `tokenize_with_mask` (T6) feeds T16 and T17; `Episode` fields from `training/env/loop.py` unchanged; `BudgetGuard` unchanged.
- **Proportion:** the plan fixes names, signatures, tests, values, gates; code bodies are left to the implementer.
- **Known weak spots, stated honestly:** GPU-h figures are assumptions until T17 measures them; the 60 %/70 %/5 pp gates are proposals for the owner to confirm at G0; B0 v2 fairness is a process control, not a guarantee (the same author builds tasks and B0); the real-clip share of the corpus depends on the owner's recordings.
