# Preregistration: Phase 0 go/no-go

Status: FINAL (2026-11-15). Finalised by Claude on the owner's instruction "Do whatever you can on your own"; every threshold below is copied unchanged from PHASES.md. Owner may amend only via a dated post-hoc section.

Written before any model is run on the spike tasks (RULES §4.6). Changes after the first run are allowed only as a new, dated section labelled post-hoc.

## Task set
- `data/tasks/dev/spike-v0.jsonl` (split `dev`, 50 tasks; sha256 `25e9d18e2ddf486aa44f261c62fc168322c77c0808333838fa85943d516c0489`).
- Tasks and reference solutions were drafted by Claude; **owner review is still pending**. If the owner later edits tasks, the edited set is a new version (`spike-v1`) and any rerun on it is reported separately, never merged with these results.
- All 50 tasks count in every headline number, including the 3 ambiguous and 3 unsupported ones.
- Failed, invalid, timed-out and errored episodes count as failures.

## Systems
- B1: base Qwen3-0.6B and Qwen3-1.7B, single run (`max_runs=1`), GGUF Q8_0 via llama-server, temperature 0.
- B2: same models with the agent loop (≤4 runs).
- X1: DeepSeek V4 Flash with the same loop, temperature 0, thinking off. Pilot on the first 20 tasks (cap $0.25 total for Phase 0); the remaining 30 run only if the pilot's cost per task fits the remaining cap. If X1 covers only 20 tasks, the primary comparison uses those 20 tasks for both systems, and the report says so.

## Primary comparison
- X1 − B2(Qwen3-0.6B) task success on the same tasks, paired bootstrap 95% CI (10,000 resamples, seed 20261115).
- Secondary: X1 − B2(Qwen3-1.7B); B2 − B1 for each size (does the loop help?).

## Decision rule
- **GO** if X1 − best(B2) ≥ 25 percentage points AND the browser loop runs F1, F4 and F7 end to end (PHASES Phase 0 exit criteria).
- **RETHINK** if best(B2) ≥ 85% (little left to train), or WebLLM/ffmpeg.wasm cannot run on the owner's laptop.
- Otherwise: discuss; record the decision and its reasons in DECISIONS.md.

## Known limitations declared in advance
- 50 hand-drafted tasks: wide CIs (±~14 points at 50%).
- Base Qwen3 runs at GGUF Q8_0, not fp16.
- Checker v0: direction of re-encoded rotations is not verified; mp4 vs mov containers are not distinguished; A/V offset is measured from stream start times only.

## Post-hoc section (2026-11-16): paraphrase robustness
Not part of the Phase 0 verdict. Owner approved (cap $0.02 for paraphrasing, budget-guarded). Question: do B0 and X1 hold up on wording the author did not write?
- Dev tasks only; no test split touched. One DeepSeek paraphrase per task, generated once.
- A paraphrase is kept only if (a) its digits match the original's exactly and (b) a second DeepSeek call, shown the gold spec, answers YES to "same meaning". Dropped ones are listed with the reason, never regenerated.
- B0 frozen first (`reports/2026-11-16-paraphrase-robustness/FREEZE.md`). Report B0 and X1 on originals vs paraphrases, same kept task set, Wilson CIs; paired difference by bootstrap.

## Post-hoc section (2026-11-16): spike-v1
Not part of the Phase 0 verdict, which stays as recorded. After the owner's task review, `data/tasks/dev/spike-v1.jsonl` was derived from spike-v0 (changes: `data/tasks/dev/spike-v1.CHANGES.md`, decision D-025) and the checker became v1.2 (implicit invariants, clockwise rotation measured from content, exact frame counts).
- spike-v0 stays unchanged (sha256 pinned in `tests/tasks/test_spike_v1.py`); its numbers are never merged with v1's. v0 results were graded by checker v0/v1.1 and are not re-graded.
- spike-v1 = 49 carried-over tasks (source `spike-v0`) + the owner's new tasks (ids `n01..`, source `spike-v1-new`, plus 2-3 new clips). Every task's reference solution must pass its gold spec under checker v1.2 (`uv run python -m eval.verify_tasks`) before any system is run.
- Systems to run once the new tasks are in: B0 at the frozen commit (tag `b0-frozen-paraphrase`, hash in `reports/2026-11-16-paraphrase-robustness/FREEZE.md`, unchanged), base Qwen3-1.7B (fair prompt, constrained decoding), and X1 (DeepSeek V4 Flash, loop, thinking off, budget-guarded). Report Wilson 95% intervals for each, split into **original** and **new** tasks, and overall.
- Limitation declared in advance: the owner wrote the new tasks after seeing the original set and the checker's behaviour; B0's patterns were not touched but the tasks may still resemble them.

## Phase 1 preregistration (2026-11-16)
**Phase 1 status: DRAFT.** Written before any Phase 1 model is evaluated; it becomes FINAL only by an explicit owner-approved edit that records the date. `eval/testlock.py` refuses every test-split run until the marker reads FINAL, and then allows each (system, checkpoint, split) once.

### Data and splits
Generator v1 (`training/taskgen`, D-027): hash-pinned splits in `data/tasks/MANIFEST.json`. Test-compositional holds out whole family combinations (`config.HELDOUT_COMBOS`); test-phrasing uses two phrasing styles (technical, indirect) that appear nowhere else; test-iid is the training distribution. test-real (about 100 hand-written tasks on owner clips) is added later and reported separately. The hand-written spike-v1 tasks stay dev-only.

### Systems
B0 (regex/preset, v2, authored from train phrasing only, frozen by tag + file hash before any test split is generated or run), B2 (base Qwen3-0.6B and 1.7B with the loop), M1 (SFT), M3 (SFT + multi-turn GRPO), X1 (DeepSeek V4 Flash with the loop). M2 (single-turn GRPO) is deferred to Phase 4 (D-031). Checkpoint selection uses **dev only**.

### Primary comparison family (Holm-adjusted across all of them; paired bootstrap 10,000 resamples, seed 20261115)
1. Q2: M1 - B2 on test-iid. 2. Q3: M3 - M1 on test-iid. 3. Q4: M3 - X1 on test-iid. 4. Q5: M3 on test-compositional and test-phrasing, each vs M1. 5. Q7: M3 - B0 per family on test-iid.
Minimum meaningful difference: 5 percentage points on test-iid. A claim needs the Holm-adjusted interval to exclude 0. Single rates use Wilson 95% intervals (D-021).

### Continue-gates (decide when to proceed, never what is reported)
Teacher pilot continues to bulk if kept-rate >= 70% overall and cache-hit ratio >= 60%. GRPO starts only if M1 reaches >= 60% dev success with <= 5% invalid actions.

### GRPO stopping rules
Cap 15 GPU-hours; stop if the no-signal group share exceeds 60% for 10 consecutive steps, if the refusal rate on supported tasks leaves `REFUSAL_RATE_BAND`, if the invalid-action rate rises for 10 steps, or if a human spot-check finds an exploit (then fix the reward in a new commit and restart from the last clean checkpoint, documenting the discontinuity).

### Controls and disclosures
Shuffled-reward run (30 steps; must not improve dev). Leakage audit (`eval/leakage.py`) of test-phrasing and test-compositional against train must stay below `LEAKAGE_JACCARD_MAX`. 50 random passed M3 outputs are inspected by hand. Single training seed unless compute allows more; the report says "single seed". B0 is hand-written by the same author as the tasks (process control: the held-out phrasing templates were not read). Teacher and X1 are the same model family. Checker blind spots: filter-made A/V offsets, first-frame rotation measurement, and no default quality floor on trimmed/reframed size tasks (D-025).
