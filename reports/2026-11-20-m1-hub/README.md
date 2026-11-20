# ffmpeg-agent-m1-0.6b (private, dev-evaluated only)

## Base model

Qwen/Qwen3-0.6B (Apache-2.0). LoRA adapter (all-linear, r=16, alpha=32, dropout 0) merged into the base, then converted to GGUF with llama.cpp b12032 and quantised to Q8_0 (D-036).

## Training data

SFT set `m1-v1`: 6,032 train / 333 validation multi-turn trajectories (1.54 M trained tokens) on synthetic FFmpeg tasks from the project's task generator v1 (22 synthetic clips + 14 real CC-licensed clips; held-out splits and the owner's own clips are not in the training data). Sources: 3,021 teacher trajectories (kept only if the checker passed), 1,896 teacher paraphrases of train requests, 1,115 programmatic oracle trajectories. Every trajectory: spec first, then run(s), then finish, ask_user or unsupported.

## Teacher

DeepSeek V4 Flash (alias resolved to DeepSeek-V4.1-Flash-1017), prompted with the project's spec-first prompt v1 on TRAIN tasks only. Terms snapshot hashes are in the teacher data card (`reports/2026-11-19-teacher-bulk/DATA_CARD.json`).

## Training recipe

Kaggle T4, 2 epochs (reduced from the configured 3 to save time), per-device batch 2 x grad-accum 8 (effective 16), lr 1e-4 cosine, warmup 0.03, max length 3072, loss on assistant turns only, fp16; 754 optimizer steps; final train loss (mean) 0.0997, eval loss 0.0777 (D-037). No GRPO: M3 is not trained (see D-040).

## Evaluation

Dev split only (300 tasks, same generator as train). No test split has been run. Greedy decoding, no constrained decoding, failed/invalid episodes count as failures, Wilson 95% intervals.

| System | dev success |
|---|---|
| B0 (regex baseline) | 178/300 = 59% [54%, 65%] |
| M1 GGUF Q8_0 | 293/300 = 98% [95%, 99%] |
| M1 HF fp16 (100-task parity subset) | 99/100 = 99% [95%, 100%] |

Recovery from a verified failing first command (dev): 225/250 = 90% [86%, 93%]. Reports: `reports/2026-11-20-m1-dev`, `-m1-parity`, `-g3-pilots` in the project repo.

## Limitations

The 98% is an in-distribution dev number: dev comes from the same generator, templates and clips as training, and 15% of dev requests are word-for-word duplicates of train requests. Expect lower numbers on unseen compositions, unseen phrasing and real user clips (held-out splits, not run). Weak spots: join + remove-audio style compositions, speed and frame-interval corrections. Needless re-encode when a stream copy suffices occurred on 8 of 31 such dev tasks. 0.6B parameters, Q8_0; single training seed.

## Licence

Project code GPL-3.0. Base model Apache-2.0. The training data includes DeepSeek-generated trajectories, subject to DeepSeek's terms; this repo is PRIVATE and the weights must not be published until those terms have been reviewed for redistribution of derived models.

## Intended use

Research and portfolio demonstration of a small agent that turns a plain-language video chore into a verified FFmpeg command through the project's agent loop (spec, run, automatic check). Not a general chat model; it expects the project's system prompt (v1) and chat template (`chat-template.jinja`).
