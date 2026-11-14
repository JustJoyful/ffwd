# Phase 0 Go/No-Go Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimum Python harness (protocol v0, probe, validator, executor, checker v0, agent loop), the 50-task spike set and baselines, and the browser + Kaggle feasibility checks needed to make the Phase 0 go/no-go call.

**Architecture:** A uv-managed Python package (`training/`, `eval/`) implements the harness against JSON Schemas in `packages/protocol`, which is the single source of truth. Models are reached through one OpenAI-compatible chat policy: local `llama-server` for Qwen3, the DeepSeek API through a budget guard. Browser feasibility lives in a throwaway Vite app under `spikes/browser/` that reuses the protocol's system prompt, allowlist and conformance cases.

**Tech Stack:** Python 3.11+ (uv, pytest, Ruff, Black, `jsonschema`, `openai`), FFmpeg 9 native, llama.cpp `llama-server` (GGUF), TypeScript strict + Vite + pnpm, `@ffmpeg/ffmpeg` + `@ffmpeg/core-mt`, `@mlc-ai/web-llm`, Vitest, Playwright, Kaggle 2×T4.

**Spec:** `PHASES.md` (Phase 0), `ARCHITECTURE.md` §3, §4, §7, §11, `EVALUATION.md` §2–§5, `RULES.md`, `DECISIONS.md` D-004, D-007, D-010, D-015.

## Global Constraints

- Python ≥ 3.11; dependencies pinned in `uv.lock`; TS deps pinned in `pnpm-lock.yaml`. Every new dependency gets a one-line justification in its commit message (RULES §6.7).
- FFmpeg is started only as `subprocess.run([...], shell=False)`. No string from a model is ever joined into a command line (RULES §1.1).
- Every `run` action passes the allowlist validator before execution. Unknown means rejected (RULES §1.2).
- The model references files only by ID. The harness assigns real paths inside the job dir (RULES §1.3).
- Limits on every run: timeout, output size cap, max 4 runs per job (ARCH §3.1).
- All tunables live in `training/config.py` (Python) and `spikes/browser/src/config.ts` (TS) (RULES §6.2).
- `protocol_version = "0.1.0"`.
- The DeepSeek lifetime cap is **$4.00** and the Phase 0 pilot cap is **$0.25**. Pilot ≤20 tasks before scaling. Thinking is off and max tokens are capped (RULES §5).
- The 50 spike tasks are split `dev` with source `spike-v0` and **never** go into a test split (PHASES Phase 0).
- Reports go to fresh `reports/<YYYY-MM-DD>-phase-0/...` dirs with `manifest.json`. A writer refuses an existing path (RULES §4.7).
- Failed, invalid and timed-out episodes count as failures in every metric (RULES §4.2).
- Commits use `type(scope): description` with **no** `Co-Authored-By` or AI attribution (CLAUDE.md).
- Licence GPL-3.0 (D-016). Clip licences are recorded in the corpus manifest.

## Review Focus

1. A Qwen3 reply wrapped in `<think></think>`, in a ```` ```json ```` fence, or followed by prose: one JSON object is extracted, otherwise the turn counts as `invalid`. It never crashes the episode. *(Test in Task 8.)*
2. An iPhone-style clip coded 1920×1080 with rotation 90 against a spec of width 1080, height 1920: the checker compares **display** dimensions, so it passes. *(Test in Task 7.)*
3. FFmpeg exits 0 but writes an empty or missing file, or times out leaving a partial file: the run reports failure, partial output is deleted, and the check fails. *(Tests in Tasks 6 and 7.)*
4. An input with no audio where the model maps `0:a`: FFmpeg's non-zero exit becomes an observation with the stderr tail and the loop continues to the next turn. *(Test in Task 6.)*
5. The process dies between the API request and the cost settlement: the worst-case reservation stays counted against the cap. *(Test in Task 10.)*

---

## File Structure

```text
pyproject.toml                    # uv project "ffmpeg-agent-py"; packages training, eval; ruff/black/pytest config
LICENSE                           # GPL-3.0 text
.github/workflows/ci.yml          # python: ruff, black --check, pytest (apt ffmpeg); js: pnpm lint/test in spikes/browser
pnpm-workspace.yaml               # members: spikes/browser
packages/protocol/
  schemas/{action,spec,probe,check,task}.schema.json
  allowlist.json                  # options (base name → value kind), encoders, decoders, filters, muxers, pix_fmts
  prompts/system-v0.txt           # byte-identical system prompt for every system (cache hits, fairness)
  conformance/validator.jsonl     # {args, inputs, outputs, ok, reason} cases; Python and TS must agree
training/
  config.py                       # every tunable listed in Task 1
  protocol.py                     # schema loading + validate(kind, obj)
  corpus/make_synthetic.py        # deterministic lavfi clips + manifest
  env/probe.py  env/validator.py  env/executor.py  env/checker.py  env/actions.py  env/loop.py
  teacher/budget.py               # BudgetGuard (append-only JSONL ledger)
  policies.py                     # ChatPolicy (OpenAI-compatible)
  grpo/toy_spike.py               # Kaggle GPU-hours/step measurement
eval/
  run_baseline.py  stats.py  report.py
  configs/{qwen3-0.6b,qwen3-1.7b,deepseek-v4-flash}.toml
  PREREGISTRATION.md
data/                             # gitignored: corpus media, ledger, job dirs
  corpus/manifest.json            # tracked (hashes, probe, licence)
  tasks/dev/spike-v0.jsonl        # tracked
spikes/browser/                   # Vite + TS strict; throwaway feasibility app
  public/_headers  vite.config.ts  src/{config,ffmpeg-check,webllm-check,memory-check,mini-loop,validator}.ts
tests/                            # mirrors training/ and eval/
```

Deliberate deferrals (later phases): TS/Python type codegen from schemas (Phase 2), `per_input` batch specs, loudness/offset/quality-floor checks (checker v1, Phase 1), sandboxing with Bubblewrap (Phase 1 rollouts), the regex baseline B0 (Phase 1).

---

### Task 1: Repo scaffold, config, CI

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `LICENSE`, `pnpm-workspace.yaml`, `.github/workflows/ci.yml`, `training/__init__.py`, `training/config.py`, `eval/__init__.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `training.config` module constants: `REPO_ROOT: Path`, `PROTOCOL_DIR = REPO_ROOT/"packages/protocol"`, `PROTOCOL_VERSION = "0.1.0"`, `FFMPEG_BIN = "ffmpeg"`, `FFPROBE_BIN = "ffprobe"`, `RUN_TIMEOUT_S = 120`, `MAX_OUTPUT_BYTES = 200 * 2**20`, `MAX_RUNS_PER_JOB = 4`, `MAX_TURNS_PER_JOB = 8`, `MAX_ASK_USER = 1`, `DEFAULT_TIME_TOLERANCE_S = 0.1`, `FPS_REL_TOLERANCE = 0.01`, `FRAME_COUNT_TOLERANCE = 1`, `STDERR_TAIL_CHARS = 2000`, `DATA_DIR = REPO_ROOT/"data"`, `CORPUS_DIR`, `JOBS_DIR`, `LEDGER_PATH = DATA_DIR/"budget-ledger.jsonl"`, `BUDGET_LIFETIME_USD = 4.00`, `BUDGET_PHASE0_PILOT_USD = 0.25`, `BOOTSTRAP_RESAMPLES = 10_000`, `BOOTSTRAP_SEED = 20261115`.

- [ ] **Step 1:** `git init`. `.gitignore` covers `data/*` except `data/corpus/manifest.json` and `data/tasks/`, plus `.venv`, `node_modules`, `dist`, `.env`. Copy the GPL-3.0 text from gnu.org into `LICENSE`.
- [ ] **Step 2:** Run `uv init --package`, edited so that `pyproject.toml` declares `requires-python = ">=3.11"`, packages `training` and `eval`, dev deps `pytest ruff black`, runtime deps `jsonschema` (schema validation) and `openai` (one client for llama-server and DeepSeek, since both are OpenAI-compatible). Ruff and Black use line length 100.
- [ ] **Step 3:** Write `tests/test_config.py::test_protocol_dir_exists_and_version` asserting `config.PROTOCOL_DIR.is_dir()` and `config.PROTOCOL_VERSION == "0.1.0"`. Run `uv run pytest tests/test_config.py -v`. Expected: FAIL (no protocol dir).
- [ ] **Step 4:** Create `training/config.py` with the constants above (comment each with its source doc, e.g. `# ARCH §3.1 turn budget`), and `mkdir -p packages/protocol/schemas`. Rerun. Expected: PASS.
- [ ] **Step 5:** Write `ci.yml` with two jobs. `python`: `apt-get install ffmpeg`, `uv sync`, `uv run ruff check .`, `uv run black --check .`, `uv run pytest`. `js`: pnpm install, `pnpm -C spikes/browser lint && pnpm -C spikes/browser test`, guarded with `if: hashFiles('spikes/browser/package.json') != ''`.
- [ ] **Step 6:** Add the "Commands" section to `CLAUDE.md` (`uv sync`, `uv run pytest`, `uv run pytest tests/path::name -v`, `uv run ruff check . && uv run black --check .`).
- [ ] **Step 7:** Commit `chore(repo): scaffold uv project, config, CI skeleton`. **(Owner)** Create the GitHub repo, push, and enable secret scanning.

---

### Task 2: Protocol v0 schemas and loader

**Files:**
- Create: `packages/protocol/schemas/{action,spec,probe,check,task}.schema.json`, `training/protocol.py`, `tests/test_protocol.py`

**Interfaces:**
- Produces: `training.protocol.validate(kind: Literal["action","spec","probe","check","task"], obj: dict) -> list[str]` (empty list means valid; messages otherwise). `load_schema(kind) -> dict`. Every schema has `"$id"` ending in `/v0.1.0/<kind>`.
- Schema contents (JSON Schema 2020-12, `additionalProperties: false` everywhere):
  - **spec:** the shape in ARCH §3.2 exactly. `family` is an array of the enum `F1`…`F12`; `outputs[].id` matches `^[a-z][a-z0-9_]{0,15}$`; `kind` is in `video|audio|image_sequence|gif`; every leaf is nullable.
  - **action:** `oneOf` discriminated by `"action"`: `spec{spec}`, `ask_user{question}`, `unsupported{reason, nearest_supported?: F1..F12}`, `run{args: string[] (1..64), inputs: id[], outputs: id[]}`, `finish{outputs: id[], note}`.
  - **probe:** ARCH §3.3 fields. Streams carry `rotation` as an integer in {0, 90, 180, 270}.
  - **check:** ARCH §3.4 exactly.
  - **task:** `{id, split: "dev"|"train"|"toy", source, request, inputs: clip_id[], gold_spec: spec|null, families, difficulty: 1..4, flags: {ambiguous: bool, unsupported: bool}, clarification: str|null, reference_runs: action.run[]|null}`.

- [ ] **Step 1:** Write tests in `tests/test_protocol.py`. `test_arch_spec_example_is_valid` uses the §3.2 example with the `kind` value set to `"video"`. `test_arch_check_example_is_valid` uses §3.4. `test_run_action_rejects_string_args` uses `{"action":"run","args":"-i x","inputs":[],"outputs":[]}` and expects non-empty errors. `test_unknown_action_rejected`. `test_spec_rejects_extra_field`.
- [ ] **Step 2:** Run `uv run pytest tests/test_protocol.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3:** Write the five schemas and `training/protocol.py` (use `jsonschema.Draft202012Validator`, cache loaded schemas, resolve `$ref` between files through a `referencing.Registry`).
- [ ] **Step 4:** Rerun. Expected: PASS.
- [ ] **Step 5:** Commit `feat(protocol): v0.1.0 schemas for action, spec, probe, check, task`.

---

### Task 3: Mini corpus

**Files:**
- Create: `training/corpus/make_synthetic.py`, `tests/conftest.py`, `tests/corpus/test_make_synthetic.py`, `data/corpus/manifest.json` (generated, tracked)

**Interfaces:**
- Produces: `make_corpus(out_dir: Path) -> list[ClipRecord]`, where `ClipRecord = TypedDict(id, file, sha256, licence, source, probe)`. CLI: `uv run python -m training.corpus.make_synthetic data/corpus`. Pytest fixture `corpus: dict[str, Path]` (session-scoped, built into `tmp_path_factory`).
- Clip IDs and recipes (`testsrc2` + `sine`, deterministic, 4 s unless noted):

| id | container / codecs | property |
|---|---|---|
| `h264_aac_1080p` | mp4, h264 + aac | baseline 16:9, 30 fps |
| `h264_vertical` | mp4, h264 + aac, 1080×1920 | 9:16 |
| `hevc_iphone` | mov, hevc (`-tag:v hvc1`) + aac | iPhone-style |
| `hevc_rot90` | mov, hevc coded 1920×1080, display rotation 90 | rotation metadata **[VERIFY: FFmpeg 9 `-display_rotation` input option vs legacy `-metadata:s:v rotate`]** |
| `vp9_opus_webm` | webm, vp9 + opus | WebM |
| `h264_noaudio` | mp4, h264 only | no audio |
| `h264_quiet` | mp4, h264 + aac sine at −40 dBFS | quiet audio |
| `h264_25fps_720p` | mp4, 1280×720 25 fps, 10 s | fps/trim/frames |
| `mpeg4_avi` | avi, mpeg4 + mp3 | legacy container |
| `h264_long` | mp4, 20 s | merge/trim/compress |
| `clip_a`, `clip_b` | mp4, same params, 3 s each | merge pair |

- [ ] **Step 1:** Write `test_make_corpus_records_valid_probe_and_hash`. For each record, the file exists, `sha256` matches, and `protocol.validate("probe", r["probe"]) == []`. Also write `test_hevc_rot90_has_rotation_90` and `test_noaudio_has_no_audio_stream`. These depend on `probe()` from Task 4, so write Task 4 before running them, or mark them `xfail` until then.
- [ ] **Step 2:** Implement with one `subprocess.run([...], shell=False, check=True)` per clip from a list of argv recipes. Add `-fflags +bitexact -map_metadata -1` so hashes stay stable on one FFmpeg build. Record `licence: "CC0-1.0 (synthetic, generated)"`.
- [ ] **Step 3 (owner):** Record 3 real clips on a phone (one iPhone HEVC if available) and add them to the manifest with `licence: "own recording, GPL-compatible"` and `source: "owner"`. Raw media stays in `data/` and is never committed.
- [ ] **Step 4:** After Task 4, run `uv run pytest tests/corpus -v`. Expected: PASS. Commit `data(corpus): synthetic mini corpus generator and manifest`.

---

### Task 4: Probe

**Files:**
- Create: `training/env/__init__.py`, `training/env/probe.py`, `tests/env/test_probe.py`

**Interfaces:**
- Produces: `probe(path: Path) -> dict` (valid `probe` schema). `display_size(probe_stream: dict) -> tuple[int, int]` swaps width and height when rotation is 90 or 270.
- Runs `[FFPROBE_BIN, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]`. Rotation comes from the stream `side_data_list` displaymatrix `rotation`, normalised with `(-r) % 360` so it lands in {0, 90, 180, 270}. fps comes from `avg_frame_rate` as a float, or null when it is `0/0`.

- [ ] **Step 1:** Write the tests: `test_probe_h264_fields` (container contains `mp4`, duration ≈ 4.0 ± 0.1, video 1920×1080, fps 30, audio aac), `test_probe_rotation_normalised` (`hevc_rot90` → 90), `test_display_size_swaps_on_rotation` ((1920, 1080) with rotation 90 → (1080, 1920)), and `test_probe_missing_file_raises` (`FileNotFoundError`).
- [ ] **Step 2:** Run them. Expected: FAIL. Implement. Rerun. Expected: PASS (and Task 3's tests now pass).
- [ ] **Step 3:** Commit `feat(env): ffprobe-based normalised probe`.

---

### Task 5: Allowlist validator + conformance cases

**Files:**
- Create: `packages/protocol/allowlist.json`, `packages/protocol/conformance/validator.jsonl`, `training/env/validator.py`, `tests/env/test_validator.py`

**Interfaces:**
- Produces: `validate_run(args: list[str], inputs: list[str], outputs: list[str], *, known_inputs: set[str], known_outputs: set[str]) -> ValidationResult`, where `ValidationResult = dataclass(ok: bool, reason: str | None)`. `uses_stream_copy_only(args) -> bool` returns True when every codec option is `copy` and no filter option is present. The checker uses it as the `re_encoded` measurement.
- File reference grammar (a decision; document it in the system prompt): files appear **only** as whole tokens `{in:<id>}` (immediately after `-i`) and `{out:<id>}` (positional, after all options for that output). Nothing else positional is allowed.
- `allowlist.json` shape: `{"options": {"-ss": "time", "-t": "time", "-to": "time", "-c": "codec", "-b": "bitrate", "-vf": "filtergraph", "-af": "filtergraph", "-filter_complex": "filtergraph", "-map": "map", "-r": "number", "-an": "flag", "-vn": "flag", "-crf": "int", "-preset": "enum:ultrafast,superfast,veryfast,faster,fast,medium,slow", "-pix_fmt": "pix_fmt", "-f": "muxer", "-movflags": "enum:+faststart", "-tag": "enum:hvc1,avc1", "-display_rotation": "number", "-frames": "int", "-q": "int", "-ar": "int", "-ac": "int", "-metadata": "metadata", ...}, "encoders": [...], "filters": [...], "muxers": [...], "pix_fmts": [...]}`. Option keys are base names. For `-c:v`, `-b:a`, `-frames:v` and `-q:v`, strip the `:stream-spec` suffix before lookup. Filters cover v1 families F1–F12 (`trim, atrim, setpts, asetpts, scale, crop, pad, transpose, hflip, vflip, fps, concat, volume, loudnorm, adelay, atempo, palettegen, paletteuse, split, format, select`). `movie`, `amovie`, `subtitles` and any file-reading filter are deliberately absent. Muxers exclude `concat`, `image2pipe` and any network muxer.
- Algorithm (not determined by the signature): walk the tokens left to right. A token starting with `-` is an option: look up its base name, consume arity 0 for `flag` or 1 otherwise, and check the value against its kind. `time` matches `^\d+(\.\d+)?$|^\d{1,2}:\d{2}(:\d{2})?(\.\d+)?$`. `codec` must be in encoders or be `copy`. `filtergraph` is split on `;` and `,` outside brackets, `[labels]` are stripped, and the name before `=` must be in filters; label tokens match `^[A-Za-z0-9_:]+$`. `map` matches `^\[?[A-Za-z0-9_:]+\]?$`. `metadata` matches `^[a-z_:]+=[A-Za-z0-9 _.-]{0,64}$`. Any value containing `/`, `\`, `..` or `^[a-z][a-z0-9+.-]*:` (a protocol) is rejected outright. Every declared input/output ID must appear exactly once and every token ID must be declared and known.

- [ ] **Step 1:** Write ~30 cases in `conformance/validator.jsonl`, each `{"name", "args", "inputs", "outputs", "ok", "reason_contains"}`. Must-reject cases include: `-i /etc/passwd`, `-i http://x/a.mp4`, `{out:o1}` replaced by `../o.mp4`, a `-vf "movie=/etc/passwd"`, `-f concat`, an unknown option `-filter_script`, `-c:v libfoo`, `;` shell metacharacters inside a value (inert but rejected by the value kind), an undeclared `{in:zz}`, and a declared output that is never used. Must-accept cases include: a stream-copy trim, scale+crop to 9:16, `transpose=1`, the concat filter over two inputs with labels, a frames-every-2s `fps=1/2` to `{out:frames}`, `-movflags +faststart`, and `-c:v libx264 -crf 23 -preset veryfast -pix_fmt yuv420p -c:a aac`.
- [ ] **Step 2:** Write `tests/env/test_validator.py::test_conformance_cases`, parametrised over every jsonl line and asserting `ok` and `reason_contains`. Add `test_stream_copy_only_detection` (`["-c","copy"]` → True, `["-c:v","copy","-vf","scale=640:-2"]` → False).
- [ ] **Step 3:** Run them. Expected: FAIL. Implement. Rerun. Expected: PASS.
- [ ] **Step 4:** Commit `feat(protocol): FFmpeg allowlist, validator, conformance cases`.

---

### Task 6: Executor

**Files:**
- Create: `training/env/executor.py`, `tests/env/test_executor.py`

**Interfaces:**
- Consumes: `validate_run` (Task 5).
- Produces: `execute(run: dict, *, input_paths: dict[str, Path], output_paths: dict[str, Path], timeout_s: int = RUN_TIMEOUT_S, max_output_bytes: int = MAX_OUTPUT_BYTES) -> RunResult`, where `RunResult = dataclass(ok: bool, rejected: str | None, returncode: int | None, timed_out: bool, stderr_tail: str, outputs: dict[str, Path])`. `output_path_for(job_dir: Path, out_spec: dict) -> Path` gives `job_dir/"out"/f"{id}.{container}"`. For `image_sequence` it is `job_dir/"out"/id/"%04d.{frames.format or 'png'}"`, and the parent dir is created.
- Behaviour: validate first (rejection means no process). Substitute placeholders. Prepend `[FFMPEG_BIN, "-hide_banner", "-nostdin", "-y"]` (`-y` is safe because outputs are harness-owned fresh paths). Use `subprocess.run(argv, shell=False, timeout=..., capture_output=True)`. On timeout, non-zero exit, missing or 0-byte output, or total size above the cap, delete every declared output and set `ok=False`.

- [ ] **Step 1:** Write the tests. `test_rejected_run_never_spawns` (monkeypatch `subprocess.run` to raise if called; args contain `http://`). `test_stream_copy_trim_produces_output` (`h264_long`, `-ss 2 -t 3 -c copy`). `test_nonzero_exit_returns_stderr_tail` (`h264_noaudio` with `-map 0:a`; `ok` is False, `returncode` is non-zero, `stderr_tail` is non-empty and ≤ `STDERR_TAIL_CHARS`). `test_timeout_deletes_partial` (`timeout_s=1` on a slow `-preset veryslow` encode of `h264_long`; `timed_out` is True and no output file remains). `test_size_cap_deletes_output` (`max_output_bytes=1000`).
- [ ] **Step 2:** Run them. Expected: FAIL. Implement. Rerun. Expected: PASS.
- [ ] **Step 3:** Commit `feat(env): validated, time- and size-limited FFmpeg executor`.

---

### Task 7: Checker v0

**Files:**
- Create: `training/env/checker.py`, `tests/env/test_checker.py`

**Interfaces:**
- Consumes: `probe`, `display_size` (Task 4); `uses_stream_copy_only` (Task 5).
- Produces: `check(out_spec: dict, output: Path, *, input_probe: dict, run_args: list[str]) -> dict` (valid `check` schema). It never raises on bad media: a probe failure becomes `{"passed": false, "error": "..."}`.
- Field rules (only fields that are set are checked; each one appends `{field, expected, actual, ok}`):
  - `container`: the format name contains the value.
  - `video.codec`, `audio.codec`, `video.pix_fmt`: exact match.
  - `video.width` and `height`: compared on **display** size.
  - `video.rotation`: probe rotation.
  - `video.fps`: relative error ≤ `FPS_REL_TOLERANCE`.
  - `audio.present`: whether an audio stream exists.
  - `time`: expected duration is `end_s - start_s` when both are set, `input_duration - start_s` when only `start_s` is set, and `end_s` when only `end_s` is set. Pass when |actual − expected| ≤ `tolerance_s` (or `DEFAULT_TIME_TOLERANCE_S`).
  - `size_max_bytes`: file size ≤ the value.
  - `frames.expected_count`: the file count in the dir is within ±`FRAME_COUNT_TOLERANCE` of the value. When only `interval_s` is set, the expected count is `floor(input_duration / interval_s)`. `frames.format` checks the extension.
  - `lossless: true`: requires `measurements.re_encoded == False`.
  - `measurements` always includes `duration_s` and `re_encoded = not uses_stream_copy_only(run_args)`.
- Multi-input tasks (F2): `input_probe` is the first input's probe. For a time check on a merge, the gold spec sets `end_s` to the summed duration, which the task author writes.

- [ ] **Step 1:** Write the tests. Build each output with `execute` from Task 6. `test_trim_passes_gold_spec` (`time {start_s: 2, end_s: 5}`, stream copy; passes, `re_encoded` is False). `test_wrong_height_fails_with_field_detail` (the failing entry has `field == "video.height"`). `test_rotated_display_dims_pass` (`hevc_rot90` remuxed with `-c copy`; the spec says width 1080, height 1920; passes). `test_lossless_fails_when_reencoded`. `test_frames_every_2s` (`h264_25fps_720p` over 10 s, `fps=1/2`, expected count 5 ± 1). `test_empty_output_fails_not_raises` (write a 0-byte file; `passed` is False and `error` is set). `test_null_fields_unconstrained` (spec with every field null except kind passes any video).
- [ ] **Step 2:** Run them. Expected: FAIL. Implement. Rerun. Expected: PASS.
- [ ] **Step 3:** Commit `feat(env): deterministic checker v0`.

---

### Task 8: Action parsing, system prompt, agent loop

**Files:**
- Create: `packages/protocol/prompts/system-v0.txt`, `training/env/actions.py`, `training/env/loop.py`, `tests/env/test_actions.py`, `tests/env/test_loop.py`

**Interfaces:**
- Consumes: `protocol.validate`, `probe`, `execute`, `output_path_for`, `check`.
- Produces:
  - `parse_action(text: str) -> dict | ParseError`, where `ParseError = dataclass(message: str)`. It strips `<think>…</think>` blocks and one optional ```` ```json ```` fence, then requires exactly one JSON object that passes `validate("action", ...)`. The same parser applies to every system, which keeps the baselines fair.
  - `Policy = Callable[[list[dict]], str]` (OpenAI-style messages in, raw text out).
  - `run_episode(task: dict, policy: Policy, *, corpus: dict[str, Path], job_dir: Path, max_runs: int = MAX_RUNS_PER_JOB) -> Episode`, where `Episode = dataclass(task_id: str, turns: list[dict], emitted_spec: dict | None, runs: int, invalid_turns: int, asked: bool, refused: bool, last_check: dict | None, end_reason: Literal["finish","unsupported","run_budget","turn_budget"])`.
  - `score(task: dict, ep: Episode) -> bool`. For an ambiguous task, `ep.asked` is set before any run. For an unsupported task, `ep.refused` holds and `ep.runs == 0`. Otherwise `ep.last_check["passed"]` must be True.
- Loop rules:
  - The first user message holds `request`, the input IDs with their probe JSON, and the required output IDs from `gold_spec.outputs[].id`.
  - Each turn appends the assistant text and one observation message (JSON string).
  - A `spec` action is recorded. The observation is `{"spec":"confirmed"}`, and checks always use the **gold** spec (ARCH §3.2, training/eval).
  - A first `ask_user` returns `task.clarification` or the fixed text `"No more information is available; proceed with your best interpretation."`. A second `ask_user` counts as invalid.
  - `run` executes, then checks every declared output against the matching gold output. The observation is `{run_ok, stderr_tail, checks}`.
  - `finish` ends the episode only if `last_check` passed; otherwise the observation is `{"error":"finish requires a passing check"}`.
  - The episode stops at `max_runs` runs or `MAX_TURNS_PER_JOB` turns.
  - B1 single-shot is `max_runs=1`.
- System prompt content (fixed copy, ≤ 1,500 tokens): the role, the five actions with one JSON example each, the `{in:id}`/`{out:id}` grammar, "one JSON object per reply, no prose", the allowlist summary (families, not the full list), and that the harness checks automatically.

- [ ] **Step 1:** Write `tests/env/test_actions.py`: `test_parses_plain_json`, `test_strips_empty_think_and_fence`, `test_trailing_prose_is_error`, `test_two_objects_is_error`, `test_schema_invalid_is_error`.
- [ ] **Step 2:** Write `tests/env/test_loop.py` with a scripted fake policy (a list of replies). `test_pass_trim_episode` (spec → run → finish; `score` is True). `test_invalid_then_recover` (garbage → run; `invalid_turns == 1`, scored True). `test_run_budget_exhausted_scores_false`. `test_ambiguous_scored_by_ask`. `test_unsupported_scored_without_runs`. `test_finish_before_pass_rejected`.
- [ ] **Step 3:** Run them. Expected: FAIL. Implement. Rerun. Expected: PASS.
- [ ] **Step 4:** Commit `feat(env): action parser, system prompt v0, agent loop and scoring`.

---

### Task 9: 50 spike tasks

**Files:**
- Create: `data/tasks/dev/spike-v0.jsonl`, `tests/tasks/test_spike_tasks.py`

**Interfaces:**
- Consumes: the `task` schema, `execute`, `check`, the corpus.
- Composition (exactly 50, every line `split: "dev"`, `source: "spike-v0"`): **34 single-family** (F1–F12 with ~3 each, at least 2 per family), **10 multi-step** (2–3 families, e.g. trim+vertical+size, HEVC→H.264+trim, frames+resize), **3 ambiguous** (`flags.ambiguous`, `gold_spec: null`, e.g. "make it shorter"), **3 unsupported** (`flags.unsupported`, e.g. "remove the person in the background", "add subtitles", "make it look cinematic"). Every non-flagged task has `reference_runs`: the owner's hand-written correct solution.

- [ ] **Step 1:** Write the tests. `test_spike_task_count_and_mix` (50 total; 3 ambiguous, 3 unsupported, 10 with ≥2 families; every family F1–F12 appears; every split is `dev`). `test_all_tasks_schema_valid`. `test_reference_runs_pass_gold_spec` (parametrised: execute each `reference_runs` step in a tmp job dir and `check` against the gold spec; must pass). This last test validates the tasks and checker v0 together.
- [ ] **Step 2 (owner writes, Claude reviews):** Write the 50 tasks. The owner phrases requests as a non-developer would. Claude may draft `reference_runs` and gold specs, but the owner reviews each one.
- [ ] **Step 3:** Run `uv run pytest tests/tasks -v`. Expected: PASS. A failing reference run means fixing the task or the checker's *cause*, never loosening a tolerance to fit (RULES §4.1). Ask the owner if unsure.
- [ ] **Step 4:** Record `sha256sum data/tasks/dev/spike-v0.jsonl` in the commit message. Commit `data(tasks): 50 hand-written spike tasks (dev split)`.

---

### Task 10: Budget guard and chat policy

**Files:**
- Create: `training/teacher/__init__.py`, `training/teacher/budget.py`, `training/policies.py`, `eval/configs/{qwen3-0.6b,qwen3-1.7b,deepseek-v4-flash}.toml`, `tests/teacher/test_budget.py`, `tests/test_policies.py`
- Modify: `training/config.py` (add `DEEPSEEK_PRICES_USD_PER_MTOK = {"input_cache_hit": None, "input_cache_miss": None, "output": None}`, `DEEPSEEK_PRICES_CHECKED = None` (date string), `DEEPSEEK_MODEL_ID = None`, `DEEPSEEK_BASE_URL = "https://api.deepseek.com"`, `TEACHER_MAX_OUTPUT_TOKENS = 512`)

**Interfaces:**
- Produces:
  - `BudgetGuard(ledger: Path, lifetime_cap_usd: float, run_cap_usd: float, run_id: str, dry_run: bool = False)` with `.reserve(max_cost_usd: float) -> str` (returns `reservation_id`, raises `BudgetExceeded` if spent + open reservations + this would exceed either cap), `.settle(reservation_id, usage: dict, cost_usd: float)`, `.spent(run_only: bool = False) -> float`, and `.cache_hit_ratio() -> float`. The ledger is append-only JSONL with records `{ts, run_id, kind: "reserve"|"settle", reservation_id, cost_usd, prompt_cache_hit_tokens, prompt_cache_miss_tokens, completion_tokens}`. A reservation without a settle counts at its full reserved value forever.
  - `cost_from_usage(usage: dict, prices: dict) -> float` and `worst_case_cost(prompt_tokens_est: int, max_output_tokens: int, prices: dict) -> float` (assumes every input token is a cache miss).
  - `ChatPolicy(base_url: str, model: str, api_key_env: str, temperature: float = 0.0, max_tokens: int, extra_body: dict | None, guard: BudgetGuard | None)`, a callable `Policy`. `policy_from_config(path: Path, guard) -> ChatPolicy` reads the TOML. Qwen configs set `extra_body = {chat_template_kwargs = {enable_thinking = false}}` **[VERIFY llama-server passes this through with `--jinja`]**.
- Rules: the guard raises `BudgetConfigError` if any price, `DEEPSEEK_PRICES_CHECKED` or `DEEPSEEK_MODEL_ID` is None. You can't spend before the owner fills them from the official pricing page. Keys come only from environment variables.

- [ ] **Step 1:** Write the tests. `test_reserve_blocks_over_lifetime_cap`. `test_reserve_blocks_over_run_cap`. `test_unsettled_reservation_still_counts` (reserve, then build a new guard on the same ledger file; `spent()` includes it, which covers the crash case). `test_settle_replaces_reservation_with_actual`. `test_unset_prices_raise_config_error`. `test_dry_run_never_calls_client` (mock). `test_cache_hit_ratio`. In `tests/test_policies.py`: `test_chat_policy_uses_guard_around_call` (mock `openai.OpenAI`; reserve happens before the create call and settle after).
- [ ] **Step 2:** Run them. Expected: FAIL. Implement. Rerun. Expected: PASS.
- [ ] **Step 3:** Commit `feat(teacher): append-only budget guard and OpenAI-compatible chat policy`.

---

### Task 11: Baseline runner, statistics, preregistration

**Files:**
- Create: `eval/run_baseline.py`, `eval/stats.py`, `eval/report.py`, `eval/PREREGISTRATION.md`, `tests/eval/test_stats.py`, `tests/eval/test_run_baseline.py`

**Interfaces:**
- Consumes: `run_episode`, `score`, `policy_from_config`, `BudgetGuard`.
- Produces:
  - CLI `uv run python -m eval.run_baseline --system {B1,B2,X1} --model-config eval/configs/<x>.toml --tasks data/tasks/dev/spike-v0.jsonl --out reports/<date>-phase-0/<system>-<model> [--offset N --limit N] [--budget-usd 0.25] [--dry-run]`. It exits non-zero if `--out` exists. B1 uses `max_runs=1`; B2 and X1 use `MAX_RUNS_PER_JOB`. X1 must pass `--budget-usd`.
  - It writes `results.jsonl` (one line per task: `task_id, families, difficulty, flags, success, runs, invalid_turns, end_reason, cost_usd`; an exception inside an episode is recorded as `success=false, end_reason="error"` and **kept**) plus `manifest.json` (`git_commit`, `protocol_version`, `ffmpeg_version`, `system`, `model`, `quant`, `temperature`, `tasks_sha256`, `offset`, `limit`, `hardware` (CPU, GPU, RAM), `started`, `finished`, `cost_usd`, `cache_hit_ratio`).
  - `eval.stats.bootstrap_ci(successes: list[bool], resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED) -> tuple[float, float, float]` (mean, low, high at 95%). `paired_diff_ci(a: dict[str,bool], b: dict[str,bool]) -> tuple[float, float, float]` over the shared task IDs. It raises if the ID sets differ (an honest denominator).
  - CLI `uv run python -m eval.report <out.md> <result_dir>...` merges dirs of the same system (pilot + rest), then writes a markdown table of success with CI overall, by family and by flag, plus the X1−B2 paired diff. It refuses to overwrite.

- [ ] **Step 1:** Write the tests. `test_bootstrap_all_true` → (1, 1, 1). `test_bootstrap_half_brackets_half` (100 alternating values; low < 0.5 < high and width < 0.25). `test_paired_diff_rejects_mismatched_ids`. `test_runner_refuses_existing_out`. `test_runner_records_episode_exception_as_failure` (a fake policy that raises; the line has `success: false` and the task count equals the input count).
- [ ] **Step 2:** Run them. Expected: FAIL. Implement. Rerun. Expected: PASS.
- [ ] **Step 3 (owner):** Fill in `eval/PREREGISTRATION.md` **before any baseline run**: the GO threshold (PHASES suggests X1 − best base B2 ≥ 25 points on the 50 tasks), the RETHINK threshold (base B2 ≥ 85%), the primary comparison (X1 vs B2-0.6B, paired bootstrap), and that all 50 tasks count, including flagged ones. Commit it separately: `eval(prereg): phase 0 go/no-go thresholds`.
- [ ] **Step 4:** Commit `eval(baselines): runner, bootstrap stats, report`.

---

### Task 12: Run the baselines

**Prerequisites (owner):** `llama-server` installed from the pinned llama.cpp release (recording version and checksum). The official Qwen3-0.6B and 1.7B GGUF at Q8_0 (closest to fp16 that fits; record the repo and file hash in the TOML). The DeepSeek terms of use read and saved to `docs/legal/<YYYY-MM-DD>-deepseek-terms.md` (date-stamped, quoting the clause on training with outputs). Prices, model ID and check date filled in `training/config.py` from the official pricing page. The current off-peak window noted.

- [ ] **Step 1:** Start `llama-server --jinja -m <qwen3-0.6b.gguf> --port 8080`. Run B1 and B2 for 0.6B, then the same for 1.7B, each to its own fresh `--out`. Expected: 50 result lines each.
- [ ] **Step 2:** Run the X1 pilot: `--system X1 --limit 20 --budget-usd 0.25` (off-peak). Record cost per task, pass rate and cache-hit ratio from the manifest. **Stop and show the owner.** Continue only if the projected cost of the remaining 30 tasks (pilot cost per task × 30) fits within the $0.25 pilot cap minus what's spent. Otherwise report X1 on 20 tasks and say so.
- [ ] **Step 3:** Run X1 on the rest with `--offset 20 --limit 30 --budget-usd <remaining>` into a new `--out`.
- [ ] **Step 4:** `uv run python -m eval.report reports/<date>-phase-0/baselines.md <all dirs>`. Commit `eval(phase0): base Qwen3 and DeepSeek baselines on spike tasks` (summaries and manifests only; job dirs stay in `data/`).

---

### Task 13: Browser spike: ffmpeg.wasm under COOP/COEP

**Files:**
- Create: `spikes/browser/{package.json,tsconfig.json,vite.config.ts,eslint.config.js,index.html,public/_headers,src/config.ts,src/main.ts,src/ffmpeg-check.ts,src/results.ts,tests/results.test.ts,e2e/isolation.spec.ts}`

**Interfaces:**
- Produces: `results.ts` with `type CheckRecord = {name: string; ok: boolean; ms?: number; detail?: Record<string, unknown>}`, `record(r: CheckRecord): void`, and `downloadResults(machineLabel: string): void` (downloads `phase0-browser-<label>.json` including `navigator.userAgent`, `navigator.hardwareConcurrency`, `navigator.deviceMemory`, and the GPU adapter info). `parseFfmpegDuration(log: string): number | null` parses `Duration: HH:MM:SS.xx`.
- Headers (both `public/_headers` and `vite.config.ts server.headers`): `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: credentialless`. The ffmpeg core (`@ffmpeg/core-mt`, exact version pinned) is copied into `public/` at build time and served from the same origin.
- Checks in `ffmpeg-check.ts` (each records a `CheckRecord`): `cross_origin_isolated` (`self.crossOriginIsolated`), `ffmpeg_mt_load` (ms), `ffprobe_available` (does the installed `@ffmpeg/ffmpeg` expose `ffprobe`? record the version), `hevc_decode` (transcode a user-picked `hevc_iphone.mov` to H.264 MP4; `ok` means exit 0 and non-empty output), and three timed chores on the user-picked `h264_long.mp4`: F1 stream-copy trim, F4 scale to 720p, F7 `fps=1/2` frames.

- [ ] **Step 1:** Run `pnpm create vite` (vanilla-ts), switch to strict TS, and add ESLint + Prettier + Vitest + Playwright, pinning exact versions.
- [ ] **Step 2:** Write `tests/results.test.ts::parses ffmpeg duration` (`"  Duration: 00:00:20.05, start"` → 20.05; garbage → null). Write `e2e/isolation.spec.ts::page is cross-origin isolated` (`page.evaluate(() => crossOriginIsolated)` against `vite preview` is true). Run `pnpm test && pnpm exec playwright test`. Expected: FAIL. Implement. Rerun. Expected: PASS.
- [ ] **Step 3 (owner):** Deploy with `wrangler pages deploy dist` to a Cloudflare Pages project. Open it, confirm `cross_origin_isolated` is true on the **deployed** URL, run the checks, and download the results JSON into `reports/<date>-phase-0/browser/`.
- [ ] **Step 4:** Add `eval/native_timing.py` (CLI `uv run python -m eval.native_timing --out reports/<date>-phase-0/native-timing.json`), which runs the same three chores' args on the same clip through `execute` (Task 6) and records wall-clock seconds as the native side of the comparison. Pin the args in one place, `packages/protocol/conformance/timing-chores.json`, and have the browser page read that same file.
- [ ] **Step 5:** Commit `feat(spike): ffmpeg.wasm feasibility page with COOP/COEP`.

---

### Task 14: Browser spike: WebLLM, memory, F1/F4/F7 loop

**Files:**
- Create: `spikes/browser/src/{webllm-check.ts,memory-check.ts,validator.ts,mini-loop.ts}`, `spikes/browser/tests/validator.test.ts`
- Modify: `spikes/browser/src/main.ts`, `spikes/browser/src/config.ts` (model IDs `Qwen3-0.6B-q4f16_1-MLC` and `Qwen3-1.7B-q4f16_1-MLC` **[VERIFY in the pinned WebLLM `prebuiltAppConfig`]**, max runs 4)

**Interfaces:**
- Consumes: `packages/protocol/allowlist.json`, `conformance/validator.jsonl` and `prompts/system-v0.txt` (imported at build time, so there's one source).
- Produces: `validateRun(args: string[], inputs: string[], outputs: string[], known: {inputs: Set<string>; outputs: Set<string>}): {ok: boolean; reason: string | null}`, the same grammar as Task 5, ported. `runMiniLoop(task: {request: string; file: File; family: "F1"|"F4"|"F7"}, engine, ffmpeg): Promise<CheckRecord>`: WebLLM `CreateWebWorkerMLCEngine`, the same system prompt, actions parsed as in Task 8, `validateRun` before every `ffmpeg.exec`, and a minimal check (duration for F1, dimensions for F4, frame count for F7, parsed from ffmpeg logs).
- Measurements: per model, the download bytes (from the progress callback), cold load ms (cache cleared), warm load ms, and decode tokens/s (from `engine.runtimeStatsText()`). For memory, `performance.measureUserAgentSpecificMemory()` (available because the page is cross-origin isolated) after the model loads, then during an F4 run on 100 MB and 500 MB inputs (the owner makes these with the corpus generator using longer durations). A tab crash is recorded manually as the result.

- [ ] **Step 1:** Write `tests/validator.test.ts::matches python conformance cases`, iterating every line in `validator.jsonl` and asserting `ok` and `reason_contains`. Run it. Expected: FAIL. Implement `validator.ts`. Rerun. Expected: PASS. This is the first real conformance check across both runtimes.
- [ ] **Step 2:** Implement the WebLLM and memory checks and the mini loop, wired to buttons in `main.ts`. Run `pnpm lint && pnpm test`. Expected: PASS.
- [ ] **Step 3 (owner):** On the deployed URL, run everything on the owner's laptop plus 1–2 other machines (label each). Save every results JSON to `reports/<date>-phase-0/browser/`. The exit criterion is that the mini loop **runs** F1, F4 and F7 end to end; the base model's pass or fail is recorded as it happened.
- [ ] **Step 4:** Commit `feat(spike): WebLLM load, memory, and in-browser F1/F4/F7 loop`.

---

### Task 15: Kaggle toy multi-turn GRPO measurement

**Files:**
- Create: `training/grpo/toy_spike.py`, `training/grpo/kaggle_toy.ipynb` (a thin notebook that clones the repo, runs `uv sync`, and calls the script), `training/taskgen/toy.py`, `tests/grpo/test_toy_tasks.py`
- Modify: `DECISIONS.md` (D-018: the multi-turn RL library choice)

**Interfaces:**
- Consumes: `run_episode`, `score`, the corpus.
- Produces: `make_toy_tasks(n: int = 16, seed: int) -> list[dict]` (F1 trims on synthetic clips, `split: "toy"`, `source: "toy-v0"`, **never** spike tasks). CLI `python -m training.grpo.toy_spike --steps 10 --ckpt-dir <dir> [--resume]` writes `toy_metrics.jsonl` (`step, seconds, gpu_hours, mean_reward, reward_std, rollouts`). Toy reward: 1.0 for `score`, −0.5 per invalid turn. LoRA on Qwen3-0.6B, fp16 (no bf16 on T4), group size 4, 4 prompts per step, `max_runs=2`, a checkpoint every 2 steps.

- [ ] **Step 1:** Check the current docs (context7 or the official sites) for which library runs a **custom multi-turn tool environment** inside GRPO rollouts: TRL `GRPOTrainer` (rollout/environment hooks), verl multi-turn, OpenPipe ART. Note T4 + vLLM compatibility and the licence. Write D-018 with context, decision, alternatives and consequences. **Ask the owner to approve it before Step 3.**
- [ ] **Step 2:** Write `tests/grpo/test_toy_tasks.py`: `test_toy_tasks_valid_and_disjoint_from_spike` (schema-valid, split `toy`, no request string or ID shared with `spike-v0.jsonl`) and `test_toy_reference_runs_pass`. Run them. Expected: FAIL. Implement `toy.py`. Rerun. Expected: PASS.
- [ ] **Step 3:** Implement `toy_spike.py` on the chosen library. Run locally for 1 step on the owner's GPU as a smoke test.
- [ ] **Step 4 (owner, Kaggle 2×T4):** Run 10 steps, interrupting the session after step 5 and rerunning with `--resume`. Expected: training continues from step 6 (proves checkpoint/resume) and `toy_metrics.jsonl` shows 10 steps. Save the metrics plus a manifest to `reports/<date>-phase-0/grpo-toy/`. Shut down the notebook.
- [ ] **Step 5:** Commit `feat(grpo): toy multi-turn GRPO throughput spike`.

---

### Task 16: Phase report and go/no-go

**Files:**
- Create: `reports/<date>-phase-0/summary.md`, `reports/<date>-phase-0/manifest.json`
- Modify: `DECISIONS.md` (new entries), `PHASES.md` (status table, ticked tasks), `PRD.md` §11 (system requirements filled in), `README.md` (status line)

- [ ] **Step 1:** Write `summary.md`. It contains the baseline table with CIs (from Task 12), the X1−B2 paired diff against the preregistered threshold, the browser results per machine (load times, tokens/s, peak memory, chore seconds browser vs native), the HEVC result, ffprobe availability, GPU-hours per GRPO step and the projected Phase 1 compute, the DeepSeek spend and cache-hit ratio, and honest limitations: a 50-task set, single seed, GGUF Q8 rather than fp16, the parse-strictness effect.
- [ ] **Step 2:** Add DECISIONS entries (D-019 onward), one per required decision: the browser-mode input size limit, system requirements, the HEVC path (browser or helper-only), the default model-size candidates, the compute plan, and **the GO / RETHINK verdict** with the numbers behind it.
- [ ] **Step 3:** Update the PHASES.md table (Phase 0 ✅, Phase 1 ⏳ Next) and the README status line.
- [ ] **Step 4:** Commit `docs(phase0): go/no-go report and decisions`.
