# M1 (SFT 0.6B, GGUF Q8_0) on final dev v1 (20 Nov 2026)

Dev split only, no test split was touched. Served as the deployment artifact: merged LoRA -> llama.cpp b12032 `convert_hf_to_gguf.py` -> `llama-quantize` Q8_0 -> `llama-server` with the agent chat template (D-028, D-036). Greedy decoding, seed 20261115, no constrained decoding, prompt v1, spec first. Failed, invalid and errored episodes count as failures. Wilson 95% intervals.

## Result

| System | overall | 1 family | 2 families | 3 families | 4 families | ambiguous | unsupported |
|---|---|---|---|---|---|---|---|
| B0 (regex baseline, frozen code, same dev) | 178/300 = 59% [54%, 65%] | 60/72 = 83% [73%, 90%] | 79/127 = 62% [54%, 70%] | 31/71 = 44% [33%, 55%] | 8/30 = 27% [14%, 44%] | 0/2 | 9/9 |
| **M1** | **293/300 = 98% [95%, 99%]** | 71/72 = 99% [93%, 100%] | 125/127 = 98% [94%, 100%] | 68/71 = 96% [88%, 99%] | 29/30 = 97% [83%, 99%] | 2/2 | 9/9 |

By request style: terse 65/67, polite 62/64, symptom 65/67, verbose 47/48.

M1 behaviour: 0 invalid turns in 300 episodes (every turn was a schema-valid action); 267 tasks needed exactly 1 run, 12 needed 2, 3 needed 3, 7 hit the 4-run limit; 11 episodes ended without a run (9 correct `unsupported`, 2 correct `ask_user`).

Failures (7/300): all `run_budget` (the 4-run limit used up without a passing check), all multi-family tasks except one single-family F6 (F9 is in 5 of the 7: F2+F9 twice, F6+F1+F9, F12+F9+F1+F4, F2+F4+F9; the others are F6 and F4+F10+F1). The model never failed by emitting a malformed action or refusing a supported task.

## What this number does and does not mean

* **It is a dev, in-distribution number.** Dev tasks come from the same generator, templates and clip pool as the training tasks, with different content keys. It measures whether SFT taught the protocol and the template-level skills. It says little about the held-out questions the project is about: test-compositional (unseen compositions), test-phrasing (unseen wording) and test-real (the owner's own clips and requests). Expect those to be lower. They are not run and are not tuned on.
* **Leakage check (run before writing this):** 0 dev task ids and 0 dev content keys appear in the teacher, paraphrase or oracle source files (4362 source train tasks). However, 44/300 dev requests are word-for-word identical to some training request (generic templated phrasing) and 11/300 dev tasks have the same input clip and gold spec as a training task under a different content key (why their keys differ was not investigated). M1 scores 246/252 = 98% [95%, 99%] on the dev tasks with neither overlap, the same as overall, so the overlap does not drive the result. The overlap is a generator property worth a line in the data card.
* **B0 is a weak yardstick**, a regex rule system. The stock Qwen3-0.6B scored 0/300 on this dev in the earlier check (that is why rejection sampling was skipped). The like-for-like question for GRPO is M1 vs M3 on the compositional split, not M1 vs B0.
* The SFT data was 50% teacher (DeepSeek, filtered by the checker and the unsupported-label rule), 31% teacher paraphrases and 18% programmatic oracle trajectories (gold-spec derived, D-032). The unsupported category is mostly oracle-written (templated reasons). M1 gets 9/9 on dev unsupported, but with n=9 the interval is [70%, 100%].

## SFT run (Kaggle, T4)

* Data: `data/sft/m1-v1` (hash in manifest): 6032 train / 333 validation examples, 1.54 M trained tokens; sources 3021 teacher, 1896 paraphrase, 1115 oracle.
* Model: Qwen3-0.6B, all-linear LoRA r=16, alpha=32, dropout 0; lr 1e-4, cosine, warmup 0.03; **2 epochs, per-device batch 2 x grad-accum 8 (effective 16)**, 754 optimizer steps; max length 3072; loss on assistant turns only.
* **Deviations from `config.SFT_HPARAMS` (3 epochs, 4 x 4):** 2 epochs and 2 x 8 were chosen for the T4's memory and the session budget. They are command-line overrides, not a config change; record a D-entry if M1 is kept as a baseline.
* Wall time about 5 h on Kaggle (started 19:00 IST, finished 00:02 IST), about 23 s per step. Training loss was about 0.085 at epoch 0.8 (from the live log).
* **Not captured:** the final train/eval loss and the full loss curve. The kernel's output folder only held the adapter (the script deletes checkpoints) and the Kaggle log was not retrievable through the CLI. No off-box checkpoint sync was used for this run (rule 8 deviation, accepted for a ~5 h job; it survived).

## Reproduce

```
uv run python -m training.export.merge --adapter data/sft/m1-v1-kaggle/adapter-final --out data/models/m1-merged/ffmpeg-agent-m1-0.6b
# to_gguf(..., quants=("q8_0",)) with LLAMA_CPP_DIR / LLAMA_QUANTIZE / LLAMA_CONVERT_PYTHON pointing at the b12032 tools
llama-server -m ffmpeg-agent-m1-0.6b-q8_0.gguf --jinja --chat-template-file packages/protocol/prompts/chat-template.jinja -ngl 99 -c 8192 -np 1 --cache-ram 0 --seed 20261115
uv run python -m eval.run_baseline --system M1 --model-config eval/configs/m1-0.6b-q8.toml --tasks data/tasks/dev/v1.jsonl --out reports/2026-11-20-m1-dev/M1-0.6b-q8
```

Eval took 18.5 minutes for 300 tasks on an RTX 3050 6 GB laptop GPU. Spend: $0 (DeepSeek ledger unchanged at $2.675 of $4).

## Not done here

* Parity check of the fine-tuned HF model vs the GGUF (the Q8_0 path is what was evaluated; HF-vs-GGUF agreement is not measured).
* No 1.7B SFT. No rejection-sampling data (stock model 0/300).
* GRPO, the test run and the preregistration FINAL remain with the owner (G3, G4).

## Addendum (20 Nov 2026, from the Kaggle log the owner pasted): SFT losses and the reason for 2 epochs

* **Reason for 2 epochs instead of 3 (owner): to save time.** Batch 2 x grad-accum 8 was for T4 memory (effective batch unchanged at 16).
* **Final losses:** train loss averaged **0.0997** over the run (first logged 0.826 at epoch 0.01, last logged 0.050 at epoch 1.99); **eval loss on the 333 validation examples 0.0777** at step 754 (the end).
* **Eval loss curve (every 50 steps, 333 val examples):** 0.2356 (step 50), 0.1647 (100), 0.1335 (150), 0.1144 (200), 0.1030 (250), 0.0958 (300), 0.0901 (350), 0.0868 (400), 0.0851 (450), 0.0822 (500), 0.0814 (550), 0.0792 (600), 0.0784 (650), 0.0778 (700), 0.0777 (750), 0.0777 (754). It fell at every evaluation and had flattened by the end (-0.0015 over the last 150 steps), with no sign of over-fitting; a third epoch would have bought very little.
* **Run:** `train_runtime` 17,340 s (4.82 h), 754 steps at about 20.7 s per step plus 16 evaluations of about 100 s each; fp16 on one Tesla T4 (the kernel saw two, `CUDA_VISIBLE_DEVICES=0`); Kaggle env torch 2.15.0+cu132, transformers 5.23.0, peft 0.21.3, trl 1.18.0, Python 3.11.18; the dataset's code snapshot was commit `4b185a8`. Exit code 0, "SFT DONE".
* Only the log tail was shared, not the file; the numbers above are copied from it, not re-measured.
