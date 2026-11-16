# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

You are helping build **ffmpeg-agent**: a browser-first video utility driven by a small, self-trained FFmpeg agent (Qwen3 0.6B/1.7B, SFT + multi-turn GRPO). The owner is a 2nd-year CSE student building a portfolio project. **He must be able to explain and defend every design decision in interviews**, so explain non-obvious choices briefly in PR descriptions and code comments, and never hide complexity behind magic.

## Read before working
1. `README.md`: what and why (glossary: chore, family, spec, probe/run/check, teacher…)
2. `PRD.md`: scope, users, chore families F1–F12, metrics
3. `ARCHITECTURE.md`: agent protocol, spec schema, runtimes, training pipeline, repo layout (§11)
4. `EVALUATION.md`: splits, baselines (B0–X2), metrics, statistics rules
5. `RULES.md`: **non-negotiable**
6. `PHASES.md`: work only on the **current phase**; check its exit criteria
7. `DECISIONS.md`: don't re-litigate settled decisions (D-001…); propose a new entry instead

## Current state
Phase 0 done (GO, D-020); **Phase 1 in progress** (plan `docs/superpowers/plans/2026-11-16-phase-1-core-model.md`, status `reports/PHASE1-STATUS.md`; nothing paid runs until the owner confirms the DeepSeek terms file). Work happens on `main`. Phase 0 plan: `docs/superpowers/plans/2026-11-15-phase-0-spike.md`. Add commands below as they come to exist, and don't make up commands before then.

## Commands
- `uv sync`: install the Python env (Python 3.11 pinned in `.python-version`; `training/` and `eval/` import from the repo root, no build step)
- `uv run pytest`: all Python tests; single test: `uv run pytest tests/env/test_checker.py::test_name -v`
- `uv run ruff check . && uv run black --check .`: lint and format check (CI runs both)
- `uv sync --group train` / `uv run --group train ...`: torch + TRL + PEFT for GRPO (not installed in CI; `tests/grpo/test_toy_spike.py` skips without it)
- `cd spikes/browser && pnpm test && pnpm lint && pnpm e2e`: browser spike unit, lint and Playwright tests
- `uv run python -m eval.verify_tasks data/tasks/dev/spike-v1.jsonl`: every task's reference solution must pass its gold spec (run on any new or edited task before evaluating systems)
- `uv run python -m training.corpus.add_clip <file> --id <id> --licence "..." --source "..."`: register an extra clip in the corpus manifest (licence required)
- `uv run python -m apps.cli.ffmpeg_agent_cli "<request>" file.mp4 --model m.gguf --llama-server /path/to/llama-server`: the CLI (spec confirmation, then run/check; success only when a check passed)
- `uv run python -m training.taskgen.build --workers 3`: regenerate the hash-pinned task splits into `data/tasks/` (writes `MANIFEST.json`)
- Tests need `ffmpeg`/`ffprobe` on PATH; corpus clips are generated into a temp dir by the `corpus` fixture

## Big-picture architecture (spans several docs)
- **`packages/protocol` is the contract.** JSON Schemas for actions, spec, probe result and check result, plus the FFmpeg allowlist. Change the schema first and bump `protocol_version` when you break compatibility.
- **The agent loop and checker exist twice**, in TypeScript (browser) and Python (training/eval/helper). They are kept in sync **only** by the shared conformance suite in `packages/protocol/conformance/`. A conformance failure blocks merge.
- **Model actions:** `spec | ask_user | unsupported | run | finish`, one JSON action per turn. **`check` is not a model action**: the harness runs it after every `run`, so the model can't skip verification. Turn budget is ≤4 runs.
- **The model never sees real paths.** It refers to input/output IDs and the harness maps them to paths inside the job dir. Protocols (`http:`, `pipe:`, `concat:` lists) and path traversal are rejected.
- **Two specs:** training rewards use the generator's **gold spec**; runtime checks use the **user-confirmed spec**. Never swap them. `null` spec fields are unconstrained.
- **Runtimes:** browser = WebLLM (MLC q4f16_1, prebuilt Qwen3 `model_lib`) + ffmpeg.wasm MT (needs COOP/COEP → Cloudflare Pages). Native = llama.cpp GGUF + static FFmpeg (CLI in Phase 1, FastAPI helper in Phase 3).
- **Offline pipeline:** taskgen (hash-pinned splits) → DeepSeek V4 Flash teacher + rejection sampling (keep only check-passing trajectories) → SFT → multi-turn GRPO on Kaggle → export MLC + GGUF → parity eval.
- Items marked **[VERIFY]** in ARCHITECTURE.md are unconfirmed assumptions. Confirm them; don't build on them blindly.

## Golden rules (summary of RULES.md)
1. **Never execute a shell string.** FFmpeg/ffprobe are invoked only with structured argument lists that pass the allowlist validator.
2. **Never weaken a check, test or metric to make something pass.** Missing, failed or partial results stay in denominators.
3. **Test data is sacred.** Held-out splits are hash-pinned; never train on, tune on, or prompt with test tasks. Phase 0 spike tasks go to `dev`, never test.
4. **Privacy:** analytics events never contain prompts, file names, file contents, paths or IPs.
5. **Budget:** every paid API call goes through the budget-guarded client (hard cap, $4 DeepSeek lifetime; off-peak only for bulk; cache-hit logging). Pilot before scaling (≤20 tasks).
6. **Security:** the helper binds to 127.0.0.1, checks Origin and pairing token, and writes only inside user-approved folders.
7. **One config source** per package (`config.ts`, `training/config.py`, `helper/config.py`); no magic numbers scattered in code.
8. **Training jobs must checkpoint and resume** (Kaggle sessions die at 12 h).
9. When a spec, request or result is ambiguous, **ask the owner**; don't guess silently.
10. Update `PHASES.md` status and add `DECISIONS.md` entries when decisions change.
11. For non-trivial changes, propose a short plan and wait for go-ahead (RULES §10).

## Conventions
- Python: 3.11+, `uv` for environments, Ruff + Black, type hints, pytest.
- TypeScript: strict mode, pnpm, ESLint + Prettier, Vitest; Playwright for browser end-to-end tests.
- Commits: `type(scope): description` (feat, fix, docs, test, refactor, perf, chore, eval, data). **No `Co-Authored-By` trailers or any Claude/AI attribution** in commits or PRs; nothing should suggest Claude made the commit.
- Reports go to fresh `reports/<date>-<milestone>/` paths with a `manifest.json` (commit, versions, hashes, hardware, seeds, costs), and are never overwritten.
- Licence: GPL-3.0 (D-016). Record the licence of every clip/model/dataset before use.

## Current phase
See the status table at the top of `PHASES.md`.
