# ffmpeg-agent *(placeholder name)*

> Describe an odd video chore in one sentence. It runs **on your own machine**, with **nothing to install, nothing uploaded**, and **the result checked**.

ffmpeg-agent is a browser-first video utility powered by a small language-model agent that I train myself. The agent turns a plain-English request ("take a frame every 2 seconds", "the iPhone video won't play in PowerPoint, fix it", "cut the first 3 s off all 40 files") into FFmpeg commands. It runs them locally, checks the output against the request, and fixes the command if needed.

The project has two goals, and both are deliberate:

1. **Product:** a free, open-source tool for non-developers who hit a video chore a few times a month.
2. **Research / engineering:** show that a **small specialist agent (0.6B–1.7B), trained with SFT + multi-turn GRPO on execution-verified rewards**, can get close to frontier agents on this narrow task at ~zero cost per edit, running entirely on the user's hardware.

**Status:** Planning complete. **Next: Phase 0 (go/no-go spike).** See [PHASES.md](PHASES.md).

---

## Documentation map

| Doc | What it answers |
|---|---|
| [PRD.md](PRD.md) | What we are building, for whom, why, and how we measure success |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How it works: agent protocol, browser runtime, helper app, model, training pipeline |
| [EVALUATION.md](EVALUATION.md) | How we measure the model honestly: task suite, baselines, metrics, statistics |
| [PHASES.md](PHASES.md) | The build plan: phases, tasks, budgets, exit criteria |
| [RULES.md](RULES.md) | Non-negotiable engineering, safety, privacy, budget and integrity rules |
| [DECISIONS.md](DECISIONS.md) | Why each major decision was made (decision log) |
| [CLAUDE.md](CLAUDE.md) | Short operating instructions for Claude Code sessions |

**Read order for a new contributor or Claude Code session:** CLAUDE.md → PRD.md → ARCHITECTURE.md → RULES.md → current phase in PHASES.md.

---

## Glossary

| Term | Meaning |
|---|---|
| **Chore** | A small, occasional video/audio task (trim, convert, extract frames, fix sync…) |
| **Chore family** | A category of chores sharing an operation type; used for task generation and metrics |
| **Spec** | A machine-checkable JSON description of what the output must look like (see ARCHITECTURE §3.2) |
| **probe / run / check** | The agent's three tools: inspect the input, execute an allowlisted FFmpeg argument list, verify the output against the spec |
| **Browser mode** | Everything runs in the tab: WebLLM (WebGPU) + ffmpeg.wasm |
| **Helper app** | Optional local app with native FFmpeg + llama.cpp, for big files, batches and GPU encoding |
| **Teacher** | The large model whose verified trajectories form the SFT data (DeepSeek V4 Flash via API) |
| **Rejection sampling** | Sampling a model many times and keeping only runs that pass `check()` |
| **Activated user** | An anonymous browser ID with ≥1 edit that passed its check |
| **Returning user** | An activated ID that completes another successful edit in a later 30-day window |

---

## Portfolio goals (what this project should prove)

- LLM post-training: SFT + multi-turn GRPO with verifiable rewards, plus reward-hacking controls
- An agent trained inside a real tool environment, not on static text
- Honest evaluation against regex, base-model and frontier baselines, with confidence intervals
- Model serving in two runtimes: WebLLM in the browser and llama.cpp native, with measured trade-offs
- A shipped product with anonymous, privacy-respecting usage analytics (activated / returning users, funnel)

Target resume bullets (fill with real numbers at the end):

> Built a local-first AI video utility (WebGPU + ffmpeg.wasm, optional native helper); trained a 0.6B/1.7B agent with SFT + multi-turn GRPO on execution-verified rewards, reaching X% success on held-out multi-step chores vs Y% for the base model and Z% for DeepSeek V4, at ~0 cost per edit.

> Launched to N activated users (M% returning within 30 days, anonymous PostHog analytics); reduced model-download drop-off from A% to B% by shipping a smaller quantized model.

---

## Licence

The project is open source under **GPL-3.0** (see DECISIONS D-016), because the browser build ships an FFmpeg core containing GPL components. Model weights are released under terms compatible with the base model's licence (verify the Qwen3 licence at release time).
