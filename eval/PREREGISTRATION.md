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
