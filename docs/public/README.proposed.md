# ffwd (repository name `ffmpeg-agent` until the planned rename)

> Describe an odd video chore in one sentence. A small model you can run on your own machine turns it into FFmpeg, runs it, and checks the result.

This repository holds the model side of ffwd: the agent protocol, the checker, the task generator, the training pipeline (SFT, then multi-turn GRPO with execution-verified rewards), the evaluation harness, and a command-line tool. The browser app is in the separate repository `ffwd-web`. The released model is **ffwd-0.6b v1.0.0**, a fine-tune of Qwen3-0.6B.

## How it works

- The model emits one JSON action per turn: `spec` (what the output must look like), `ask_user`, `unsupported`, `run` (an allowlisted FFmpeg argument list), `finish`.
- After every `run` the harness, not the model, probes the output and checks it against the spec. At most 4 runs per job. Success counts only when a check passed.
- The model never sees real file paths; protocols, shell strings and path traversal are rejected (`packages/protocol`, the shared schemas and conformance suite, is the contract between the Python and TypeScript implementations).

## Results (read the limitations next to them)

Held-out splits are generated tasks (900 across three test splits), run once, one training seed.

| System | Success |
|---|---|
| ffwd-0.6b, browser build (Q5_K_M, wllama on WebGPU) | 855/900 (95.0%) |
| ffwd-0.6b, native Q8_0 (the evaluated file) | 867/900 (96.3%) |
| SFT-only parent (M1) | 866/900 |
| Stock Qwen3-0.6B inside the same loop | 0/900 |
| Frozen regex baseline | answers `unsupported` on 40% of supported tasks |

The browser row is 1.33 percentage points below native (95% CI [-2.67, -0.11]); the preregistered non-inferiority guard is not shown for it. Full tables, preregistered tests and caveats: `reports/2026-11-23-phase-1/summary.md` and `LIMITATIONS.md`.

## Limitations (short version)

- The test tasks are generated from 35 clips (22 synthetic, 13 CC BY 3.0 cuts). Success on generated tasks is not success on your clips; the real-clip split was not part of this release.
- GRPO did not raise accuracy over the SFT parent; it reduced needless re-encodes (9% to 2% on one split). One training seed per system.
- The stated spec is materially wrong in about a fifth of test-iid episodes even when the output passes (success is graded on the gold spec); the spec is shown for confirmation before running (CLI). Two systematic spec bugs (rotation width/height, speed-change end time) are known.
- Quantisation matters: Q4_K_M scored 60/100 on a dev sample; do not use it.
- WebGPU on one Intel integrated GPU produced garbage for prompts over about 880 tokens (see the canary report); CPU worked on the same machine.
- Only the allowlisted FFmpeg features are supported; long or very large files are better served by the native tool.

## Get the model

Weights, GGUFs and the model card: Hugging Face `JustJoyful/ffwd-0.6b` (and the GitHub release). Verify with `sha256sum -c --ignore-missing SHA256SUMS`. The agent chat template (`chat-template.jinja`) is required; the stock Qwen3 template is wrong for this model.

## Run it

```
uv sync
uv run python -m apps.cli.ffmpeg_agent_cli "cut the first 3 seconds" clip.mp4 \
  --release releases/ffwd-0.6b-v1.0.0 --llama-server /path/to/llama-server
```

Needs `ffmpeg`/`ffprobe` on PATH (the pinned FFmpeg 5.1.1 is installed with `uv run python -m training.env.ffmpeg_pin install`) and a llama.cpp `llama-server` (tested with b12032). The CLI shows the spec for confirmation, runs, and checks.

## Reproduce

`uv run pytest` (tests need ffmpeg), `uv run ruff check . && uv run black --check .`, task generation `uv run python -m training.taskgen.build`, evaluation `uv run python -m eval.run_baseline ...`. Training uses Kaggle T4 notebooks (`training/sft`, `training/grpo`). Test splits are hash-pinned and single-run locked (`eval/testlock.py`).

## Documents

`PRD.md`, `ARCHITECTURE.md`, `EVALUATION.md` (splits, baselines, statistics), `RULES.md`, `PHASES.md`, `DECISIONS.md` (decision log), `docs/hf-cards/` (model and data cards).

## Licence

Code: GPL-3.0-only (`LICENSE`). Model weights: Apache-2.0 (Qwen3 base licence). Data: generated tasks CC BY 4.0; each clip keeps its own licence. See `THIRD_PARTY_NOTICES.md`.
