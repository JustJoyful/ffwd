# RULES: ffwd

These rules are **non-negotiable** for every contributor, including Claude Code sessions. If a rule blocks progress, stop and ask the owner; don't work around it. Changing a rule requires a DECISIONS.md entry.

---

## 1. Safety & execution
1. **No shell, ever.** FFmpeg/ffprobe/llama.cpp are started with argument lists (`subprocess.run([...], shell=False)`, worker message arrays). Strings from the model are never concatenated into a command line.
2. **Allowlist first.** Every `run` action passes the protocol validator (options, codecs, filters, muxers, filter-graph parse) **before** execution. Unknown → rejected, not "probably fine".
3. **Paths belong to the harness.** The model refers to input/output IDs; the harness assigns real paths inside the job directory or user-approved folders. Reject protocols (`http:`, `pipe:`, external `concat:` lists, etc.) and path traversal.
4. **Limits on every run:** timeout, output size cap, max runs per job.
5. **Outputs never overwrite inputs.** Failed outputs are deleted or clearly marked as failed.
6. **Training rollouts run sandboxed** (isolated temp dirs; Linux: fail-closed sandbox; no network inside the sandbox).

## 2. Helper app security
1. Bind to `127.0.0.1` only; never `0.0.0.0`.
2. Accept requests only from the official site Origin **and** with a valid pairing token.
3. File access only inside folders the user selected in the helper.
4. Protocol version must match; mismatch → refuse with a clear message.
5. Bundled binaries are downloaded only from pinned URLs and verified by checksum.
6. Security tests (cross-origin, bad token, traversal, shell metacharacters) must pass in CI before any helper release.

## 3. Privacy
1. **Media never leaves the device** in browser mode or helper mode.
2. Analytics payloads contain **only categories and numbers**. **Forbidden:** prompts, request text, file names, paths, file contents, IP, any free-text field. An automated test inspects every event schema for forbidden fields.
3. Never call PostHog `identify`. Autocapture and session replay stay off. IP capture is disabled at the project level.
4. The privacy page states exactly what is collected, in plain language, and is updated whenever the event list changes.
5. Real-user clips used in `test-real` require explicit permission and must be licence-clean; they are never published unless the owner of the clip agrees.

## 4. Correctness & integrity
1. **Never weaken a check, test, schema or metric to make something pass.** Fix the cause or report the failure.
2. **Denominators are honest:** failed, partial, timed-out and malformed runs stay in every metric.
3. **The checker is code, not a model.** No LLM judgement decides pass/fail.
4. **Training rewards use the gold spec; runtime checks use the user-confirmed spec.** Never swap these.
5. **Test splits are hash-pinned and sacred:** never used for training, reward tuning, checkpoint selection, few-shot examples, teacher prompts or paraphrase seeds. Checkpoints are selected on `dev`. Running a teacher/frontier model as an **evaluation baseline** on test splits is allowed; using any of those outputs for training is not.
6. **Predeclare** main comparisons in `eval/PREREGISTRATION.md` before the first test run; post-hoc analyses are labelled post-hoc.
7. Reports are immutable: write to fresh paths; never overwrite. Every report has a manifest (commit, versions, hashes, hardware, seeds, costs).
8. **Two checkers, one truth:** the TS and Python checkers must pass the same conformance suite. A conformance failure blocks merge.
9. Null and negative results are reported with the same care as positive ones.

## 5. Budget & external services
1. All paid API calls go through the **budget-guarded client**: hard dollar cap (configurable, default $4 lifetime), per-run cap, dry-run mode, cost logging.
2. **Pilot before scaling:** ≤20 tasks first; record cost per task, pass rate and cache-hit ratio; then scale.
3. Bulk teacher runs happen **off-peak** (check the current DeepSeek pricing page first); thinking mode off; max output tokens capped; system prompt + tool definitions byte-identical across calls for cache hits; log `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`.
4. Record teacher model ID, date and a snapshot/link of its terms of use in the data card.
5. Kaggle: always checkpoint/resume; shut down idle sessions; log GPU-hours per run.
6. API keys and tokens live in environment variables / secret stores, **never in git**. CI secret scanning is enabled.

## 6. Engineering standards
1. **Python:** 3.11+, `uv` lockfiles, Ruff + Black, type hints on public functions, pytest. **TypeScript:** strict mode, pnpm lockfile, ESLint + Prettier, Vitest; Playwright for end-to-end tests.
2. **One config module per package.** No magic numbers in business logic.
3. **Schemas are the contract:** change `packages/protocol` first, regenerate types, bump `protocol_version` when the change breaks compatibility.
4. Tests accompany behaviour changes: unit tests for validators/checkers, conformance cases for protocol changes, eval evidence for model or reward changes.
5. Commits: `type(scope): description` (feat, fix, docs, test, refactor, perf, chore, eval, data). Small, focused PRs.
6. Deterministic seeds for data generation and training; record them.
7. Dependencies are pinned; new dependencies need a one-line justification in the PR.

## 7. Model & data
1. Model versions follow `agent-v{major}.{minor}-{size}` and appear in configs, reports and analytics events.
2. Every published model has a model card: base model, data sources, teacher, training recipe, eval results with CIs, known limitations, licence.
3. Every dataset has a data card: generator version, seeds, split hashes, family distribution, teacher usage and cost.
4. Every exported format (MLC, GGUF Q4/Q8) gets a parity eval before release.
   - *Amendment (23 Nov 2026, owner decision, D-049/D-050; no rule change):* the exported formats are now GGUF only (one artifact, Q5_K_M, served to the browser by wllama, to the helper and to the CLI by llama.cpp); the MLC export was tried and dropped. The rule is unchanged and now reads: every exported format, quantisation and runtime build (including a new wllama or llama.cpp version) gets a parity eval on the same seeded dev sample against its pass criteria before release. The original wording above is kept as written.
5. The licence of every third-party asset (clips, datasets, models) is recorded before use.

## 8. Product & UX honesty
1. Never claim an edit succeeded unless the check passed.
2. Out-of-scope requests get a plain `unsupported` answer, never a guessed edit.
3. System requirements and limitations are stated on the site, not hidden.
4. Platform presets (e.g. upload size limits) cite a dated source in code comments and are re-verified before release.

## 9. Documentation & decisions
1. Update the `PHASES.md` status and phase report at the end of each phase.
2. Any change to a settled decision → new entry in `DECISIONS.md` (context, decision, alternatives, consequences).
3. Keep `README.md` limitations current; never remove a known limitation without evidence.

## 10. Working with Claude Code
1. Work only on the current phase; if a task belongs to a later phase, note it rather than doing it.
2. For non-trivial changes, propose a short plan first and wait for the owner's go-ahead.
3. Explain non-obvious design choices in PR descriptions so the owner can defend them in interviews.
4. If a spec, data result or test outcome is ambiguous, **ask** instead of assuming.
