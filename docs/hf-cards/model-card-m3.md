---
# DRAFT front matter for a PRIVATE Hugging Face model repo. Not pushed anywhere.
# Repo id is not decided: TODO(owner): choose the repo id (the repo still uses ffmpeg-agent-* names until the planned ffwd rename, D-046).
# Weights licence is not decided in the repo (D-016 only says "compatible with the base model licence, verify at release").
# TODO(owner): choose weights licence
license: other
license_name: todo-owner-choose-weights-licence
base_model: Qwen/Qwen3-0.6B
base_model_relation: finetune
language:
  - en
pipeline_tag: text-generation
tags:
  - gguf
  - llama.cpp
  - qwen3
  - ffmpeg
  - video
  - agent
  - function-calling
  - grpo
  - reinforcement-learning
---

> DRAFT: for a PRIVATE repo only. Nothing in this file or the weights it describes may become public until the DeepSeek terms have been reviewed for redistribution of models trained on DeepSeek-generated data (owner's standing rule). Local draft, not pushed. Every `TODO(owner)` below needs an answer before use.

# ffwd M3 (ffmpeg-agent-m3-0.6b): a 0.6B FFmpeg agent trained with SFT and multi-turn GRPO

(The repo, Hugging Face and Kaggle identifiers still say `ffmpeg-agent` until the planned rename to ffwd, D-046.)

## What it is

M3 is Qwen3-0.6B fine-tuned in two stages for one narrow job: turn a plain-language video chore ("cut the first 3 seconds", "make this a GIF", "compress to under 10 MB") into a verified FFmpeg command through a small agent loop.

- **M1 (the SFT parent)**: Qwen3-0.6B, LoRA SFT on 6,032 multi-turn trajectories. Private repo `JustJoyful/ffmpeg-agent-m1-0.6b`.
- **M3 (this model)**: M1 plus multi-turn GRPO, **checkpoint-60 of a 60-step run** (the last clean checkpoint of the run, a rule fixed before any dev result, D-045). The LoRA adapter was merged into the weights and converted to GGUF with llama.cpp b12032; **the Q8_0 GGUF is what ships and what was evaluated.**

The model emits **one JSON action per turn**:

| action | meaning |
|---|---|
| `spec` | state what the finished output must look like (the first action; a `run` before a `spec` is rejected) |
| `ask_user` | the request is missing something; may ask once |
| `unsupported` | the request cannot be done with FFmpeg operations (e.g. subtitles, object removal); names the nearest family or null |
| `run` | one FFmpeg invocation as a structured argument list (never a shell string), with input and output ids |
| `finish` | done; only valid after a run that passed its check |

**`check` is not a model action.** The harness runs an automatic check after every `run` and reports pass or fail back to the model. In the product the check runs against the spec the user confirmed; in training and evaluation it runs against the task's gold spec (the generator's spec), never the model's own stated spec. The model never sees real file paths: it refers to input and output ids and the harness maps them. At most 4 runs per job. FFmpeg arguments pass an allowlist validator (no `-y`, no protocols, no path traversal).

The twelve chore families (F1 to F12): trim, merge, compatibility convert, resize/crop, rotate/flip, compress to a size, extract frames, GIF, audio extract/remove, volume/loudness, A/V sync offset, speed/fps.

## Intended use

Research and portfolio demonstration of a small specialist agent inside its own loop: system prompt v1 (`system-v1.txt`), the agent chat template (`chat-template.jinja`), the spec-first protocol, and the harness check. The target product is a local, browser-first video utility for non-developers. It is **not** a general chat model, it does not give reliable answers outside the loop, and without the harness check its commands are unverified.

Out of scope: arbitrary FFmpeg use, other media tasks (subtitles, stabilisation, colour grading, object removal are all `unsupported`), safety-critical or irreversible edits without the confirmation and check steps, and any use that bypasses the argument allowlist.

## How to run

Files (all part of the repo): `ffmpeg-agent-m3-0.6b-q8_0.gguf` (639,443,520 bytes; sha256 `0fa2333c66e4b8697465e5753f4ef4b8ada40ee3f77a234659afb223e382e1b1`, recorded in `reports/2026-11-23-phase-1/manifest.json`), `chat-template.jinja` (sha256 `8d12c21330339015cf3856b2c8fd0ade15556f92c87958d3426b832bae029af5`), `system-v1.txt` (sha256 `56e7d7217b97c122662235cceb96acbf62bd822c6fec25f880035bfff805c724`).

**Important: use the custom chat template, not the stock Qwen3 one.** The agent template is stock Qwen3 non-thinking minus tools and reasoning, with the empty `<think>\n\n</think>\n\n` block kept in **every** assistant turn (D-026). Stock templates (HF, llama.cpp `--jinja`, WebLLM) drop that block from earlier turns, so the model would see contexts it was never trained on. Therefore:

- pass `--chat-template-file chat-template.jinja` to llama.cpp,
- do **not** pass `chat_template_kwargs` or `enable_thinking` (the switch does not exist in this template),
- do not rely on a template embedded by another converter.

Server command used for all evaluations (llama.cpp b12032, greedy decoding, `temperature = 0.0`, `max_tokens = 512`):

```
llama-server -m ffmpeg-agent-m3-0.6b-q8_0.gguf \
  --jinja --chat-template-file chat-template.jinja \
  -ngl 99 -c 8192 -np 1 --cache-ram 0 --seed 20261115
```

The user message is a JSON object with `request`, `inputs` (ids plus a probe: duration, streams, codecs, sizes, rotation) and `outputs` (ids); the system prompt is `system-v1.txt` (hash above). The loop itself (spec first, run, automatic check, up to 4 runs) lives in the project repo; the simplest way to use the model is the project's CLI:

```
uv run python -m apps.cli.ffmpeg_agent_cli "<request>" file.mp4 --model ffmpeg-agent-m3-0.6b-q8_0.gguf --llama-server /path/to/llama-server
```

The CLI shows the spec for confirmation, then runs and checks; it reports success only when a check passed. Project code: `JustJoyful/ffmpeg-agent` (private GitHub; GPL-3.0). TODO(owner): confirm the repo link to put here once the repos are public or renamed.

## Training

1. **SFT (M1).** Qwen3-0.6B, all-linear LoRA r16 / alpha 32 / dropout 0, lr 1e-4 cosine, warmup 0.03, max length 3072, loss on assistant turns only, fp16, 2 epochs, per-device batch 2 x grad-accum 8 (effective 16), 754 optimizer steps, one Kaggle T4. Mean train loss 0.0997, eval loss 0.0777 (D-037). The configured default was 3 epochs and batch 4 x 4; the 2-epoch run was a time-saving deviation, not tuned on dev. SFT data: see Data provenance.
2. **Multi-turn GRPO (M3).** Started from merged M1. Reward v1 (weights `pass 1.0`, `partial 0.3`, `efficiency 0.1`, `clarify 0.5`, `invalid -0.5` per invalid action, capped; `spec_acc` weight 0, D-043); group size 8, 8 prompts per step (effective batch 64), lr 1e-5, KL beta 0.0, rollout temperature 1.0, LoRA r16 / alpha 32 all-linear, 60 steps over a pool of 358 prompts (249 unique contents) drawn from TRAIN tasks only (pool defined by reward variance without `spec_acc`, D-045). Rollouts run the real loop with the real checker against each task's gold spec, so the reward is the harness verdict. Kaggle T4, 10.51 GPU-h over 60 steps. The run hit two CUDA OOMs and was resumed from checkpoints (step 30, then step 50 with micro-batch 4, same effective batch); no preregistered stop rule fired. A 30-step shuffled-reward control passed before the main run (D-045).
3. **Single seed.** One training run per system. The code default seed for GRPO is 20261116 (`config.TASKGEN_SEED`) and the evaluation bootstrap/server seed is 20261115. TODO(owner): confirm the seeds actually passed to the SFT and GRPO Kaggle runs (the Phase 1 manifest records only "single seed").

GRPO telemetry (training-set rollouts, not test performance): mean over the first and last 10 steps, pass rate 0.822 to 0.916, mean reward 0.866 to 0.987, runs per rollout 1.637 to 1.378, invalid-action rate 0.036 to 0.022 (`reports/2026-11-23-phase-1/telemetry.md`). Part of the late rise is a second pass over the pool's prompts (one epoch is about 45 steps), so dev and test, not training curves, are the evidence.

## Evaluation

All numbers are for the **native GGUF Q8_0 path in llama.cpp** (owner condition, D-028). The browser (MLC q4f16_1) number comes from a Phase 2 parity check that has not been done. Systems: B0 frozen regex baseline, B2 stock Qwen3-0.6B in the same loop, M1 SFT, M3 (this model), X1 DeepSeek V4 Flash teacher in the same loop. One run of each system on each test split, preregistered (fixed-sequence, alpha 0.05, preregistration FINAL before any test split ran). Success is graded against the task's GOLD spec (`training/env/loop.py`), never against the spec the model states; the stated spec is scored only by the separate material-spec-error metric. Greedy decoding; Wilson 95% CIs; failed, timed-out, malformed and errored episodes count as failures.

Tasks are **generated** tasks (splits below), not real user clips.

| System | test-compositional | test-iid | test-phrasing | test-iid (dedup) | runs/task (iid) | re-encode rate |
|---|---|---|---|---|---|---|
| B0 | 125/200 = 62% [56%, 69%] | 281/500 = 56% [52%, 60%] | 129/200 = 64% [58%, 71%] | 212/396 = 54% [49%, 58%] | 0.87 | 7% |
| B2 | 0/200 = 0% [0%, 2%] | 0/500 = 0% [0%, 1%] | 0/200 = 0% [0%, 2%] | 0/396 = 0% [0%, 1%] | 0.00 | n/a |
| M1 | 194/200 = 97% [94%, 99%] | 485/500 = 97% [95%, 98%] | 187/200 = 94% [89%, 96%] | 383/396 = 97% [94%, 98%] | 1.05 | 9% |
| M3 | 194/200 = 97% [94%, 99%] | 485/500 = 97% [95%, 98%] | 188/200 = 94% [90%, 97%] | 385/396 = 97% [95%, 98%] | 1.03 | 2% |
| X1 | 195/200 = 98% [94%, 99%] | 483/500 = 97% [95%, 98%] | 188/200 = 94% [90%, 97%] | 382/396 = 96% [94%, 98%] | 0.99 | 9% |

Material spec error rate (container, resolution, time range, lossless, requested codec; lower is better; descriptive, not preregistered):

| System | test-compositional | test-iid | test-phrasing |
|---|---|---|---|
| B0 | n/a (emits no spec) | n/a (emits no spec) | n/a (emits no spec) |
| B2 | n/a (emits no spec) | n/a (emits no spec) | n/a (emits no spec) |
| M1 | 34/200 = 17% [12%, 23%] | 107/439 = 24% [21%, 29%] | 42/171 = 25% [19%, 32%] |
| M3 | 28/200 = 14% [10%, 19%] | 97/439 = 22% [18%, 26%] | 38/171 = 22% [17%, 29%] |
| X1 | 20/200 = 10% [7%, 15%] | 91/439 = 21% [17%, 25%] | 31/171 = 18% [13%, 25%] |

Preregistered comparisons (fixed-sequence, alpha 0.05; b - a, paired bootstrap; lower is better for runs and needless-or-fail):

| Comparison | split | n | diff [95% CI] | raw p | status |
|---|---|---|---|---|---|
| Q2 M1-B2 | test-iid | 500 | +97.000 pp [+95.400, +98.400] | 0.0001 | rejected |
| Q7 M3-B0 | test-phrasing | 200 | +29.500 pp [+22.500, +36.500] | 0.0001 | rejected |
| Q3a M3-M1 needless-or-fail | test-iid+test-phrasing | 90 | -11.111 pp [-18.889, -4.444] | 0.0010 | rejected |
| Q3b M3-M1 runs | test-iid | 458 | -0.024 [-0.061, +0.011] | 0.1982 | NOT rejected: sequence stops |
| Q4 M3-X1 | test-iid | 500 | +0.400 pp [-1.600, +2.400] | - | descriptive (after the stop) |

Guard (M3 - M1 success, test-iid+test-compositional+test-phrasing): +0.11 pp, one-sided 97.5% lower bound -0.89 pp against -2.0 pp: **met**. Efficiency claim: **yes** (needs Q3b or Q3a rejected AND the guard met).

What this says in plain words: M3 and M1 are level on success (867/900 vs 866/900 on the three generated test splits). GRPO's measurable effect is **fewer needless re-encodes when a stream copy would do** (Q3a, n = 90, one training seed); the runs-per-task difference (Q3b) is not significant, so the sequence stopped and the M3 vs teacher comparison (Q4) is descriptive only. We do not claim M3 matches the teacher. Per-family and per-difficulty results: `reports/2026-11-23-phase-1/by_family.csv` in the project repo.

Quantisation (dev only, the same 100 seeded dev tasks, greedy; `reports/2026-11-22-m3-q4km-parity`):

| | Q8_0 | Q4_K_M |
|---|---|---|
| success | 97/100 = 97% [92, 99] | **60/100 = 60% [50, 69]** |

Paired Q4 - Q8: -37 pp, 95% CI [-47, -28]. **Q8_0 ships; do not use the Q4_K_M GGUF.**

## Limitations

- **Do not quantise to 4 bits.** M3 at Q4_K_M scores 60/100 against 97/100 at Q8_0 on the dev parity sample: 4-bit visibly damages this 0.6B fine-tune's format discipline (12 episodes with an invalid action, typically a forbidden `-y` flag or malformed JSON).
- **Browser 4-bit build is untested.** The browser runtime plans an MLC q4f16_1 build (also 4-bit). That conversion has not been tested; the browser model may be materially worse than the numbers above until it passes the same parity check on the same dev sample, and must not be called M3 before then. Other quants (Q5_K_M, Q6_K, Q4 with an importance matrix) are not part of the Phase 1 claims.
- **The material spec error rate is high even where success is high** (M3 22% on test-iid against 97% success). Success is graded against the task's gold spec, never against the spec the model states, so a model can state a wrong spec and still produce a correct output; this metric scores the stated spec separately and is descriptive only (not preregistered). In the product the user confirms the model's spec and the runtime check uses it, so a wrong stated spec would be shown to the user and checked against; that is why it matters.
- **Two known systematic spec bugs, inherited from M1 (D-043):** width and height are not swapped after a rotation (35% of rotate tasks on dev vs 7% elsewhere), and `end_s` is stated as source time after a speed change (51% vs 3%). GRPO gave spec accuracy no reward, so it did not fix them; a data fix is a post-Phase-1 item.
- **One training seed per system.** The intervals cover test-set sampling noise only, not training-run variance. M1 vs M3 differences are one run each.
- **Generated-task results are not real-clip results.** The splits are generated from a 35-clip corpus (22 synthetic plus 13 CC-licensed clips and derivatives); the success rate on real user clips is unknown. The owner-recorded `test-real` set is a later-phase addendum and has not been run.
- **test-iid has near-duplicate requests of training requests** (104 of 500 are exact-duplicate requests of train requests); the table shows the full split and the deduplicated subset (396) side by side.
- **Efficiency claim is narrow:** it rests on Q3a (n = 90) plus the guard.
- **Scores are for the harness, not the bare model.** B2 (stock Qwen3-0.6B with the same loop) scores 0/900 and B0 (regex) 62%/56%/64%: the loop alone does not make a small model work, and the check does real work.
- **FFmpeg version gap.** Evaluation used FFmpeg 5.1.1 (static); the browser build is ffmpeg.wasm 5.1.4. A behavioural gap is expected to be small but is unmeasured.
- Use without the harness check, other prompts, other templates or sampling at high temperature are untested.

## Data provenance

Full detail in the data card (`docs/hf-cards/data-card-corpus-and-tasks.md`). In short:

- **SFT data (M1):** 6,032 train and 333 validation trajectories (1.54 M trained tokens) on synthetic FFmpeg tasks from the project's task generator v1, on train tasks only: 3,021 teacher trajectories (kept only if the checker passed and the label was accepted), 1,896 teacher paraphrases of train requests (a copy of a kept trajectory with only the request reworded), 1,115 programmatic oracle trajectories. Held-out splits and the owner's own clips are not in training data.
- **GRPO data (M3):** a pool of 358 train-split prompts (249 unique contents) drawn from the train file and a hash-pinned train-only `hard-v1` file; no dev or test task.
- **Teacher:** DeepSeek V4 Flash (alias resolved to DeepSeek-V4.1-Flash-1017), thinking off, prompted with `system-v1.txt` on TRAIN tasks only, through a budget-guarded client. **The training data therefore contains DeepSeek-generated model outputs.**
- **DeepSeek terms: review pending.** The data card records a snapshot of DeepSeek's Open Platform Terms (section 4.2 says outputs may be used for training other models, including distillation; the owner read it on 2026-11-19). The owner's standing rule is that nothing becomes public until the DeepSeek terms are reviewed, including for redistribution of derived models. That review is **not done**; this is why the repo is private.
- **Corpus clips:** CC0 synthetic clips and Blender Foundation CC BY 3.0 clips (Tears of Steel, Big Buck Bunny); attribution lines are in the data card. Owner-recorded clips are excluded from training and dev.

## Licence

- **Base model:** Qwen/Qwen3-0.6B is licensed **Apache-2.0** (read from the front matter of the base model's Hugging Face card, `license: apache-2.0`, on 2026-11-23; its card names Qwen/Qwen3-0.6B-Base as its own base model).
- **Project code:** GPL-3.0 (D-016), because the browser build ships an FFmpeg core containing GPL components.
- **These model weights:** TODO(owner): choose weights licence. The repo records only that weights should be under terms compatible with the base model licence (D-016, README). Also depends on the pending DeepSeek terms review (training data includes DeepSeek outputs).
- **Training clips:** per-clip licences in the data card (CC0-1.0 for synthetic clips, CC BY 3.0 for the Blender Foundation clips, with attribution).

## Files

`ffmpeg-agent-m3-0.6b-q8_0.gguf`, `chat-template.jinja`, `system-v1.txt`, `SHA256SUMS`. TODO(owner): decide whether the LoRA adapter of checkpoint-60 (currently on the private checkpoint repo `JustJoyful/ffmpeg-agent-ckpt-grpo`) is also uploaded, as it was for M1.
