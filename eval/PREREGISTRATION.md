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
