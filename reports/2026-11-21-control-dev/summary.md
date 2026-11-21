# Shuffled-reward control: dev evaluation of checkpoint-30 (21 Nov 2026)

**The control PASSES.** A model trained 30 steps on rewards permuted within each group did not improve on dev and kept the output format. Dev only; no test split was touched.

## What was run
Kernel `justjoyful/ffmpeg-agent-grpo-auto` version 8, mode `control`, started by the owner from the web UI (attempt 2; attempt 1 died of an OOM, `reports/2026-11-21-control-attempt1/`): 30 steps, group 8, 8 prompts per step, rewards shuffled within groups (seed 20261115), pool of 358 prompts (`reports/2026-11-20-grpo-pool/pool-ids.txt`) + `hard-v1`, one T4, generation chunk 8, a checkpoint pushed every 10 steps to `JustJoyful/ffmpeg-agent-ckpt-grpo-control`. checkpoint-30 was merged onto M1 (`eval.grpo_checkpoint_dev prepare`), converted to Q8_0 GGUF (llama.cpp b12032) and run exactly like M1 on the 300 dev tasks: same server arguments, greedy, seed 20261115, prompt v1, spec first (`run_baseline --system M3`; the harness has no control label, "M3" is only the slot name).

## The pass rule and the result (`judgement/judgement.json`)
Pass iff (a) dev success is not above M1's 95% Wilson interval and (b) format validity holds (at most 5% of episodes with an invalid action).

| | dev success |
|---|---|
| M1 (SFT) | 293/300 = 97.7% [95.3, 98.9] |
| **control, checkpoint-30** | **294/300 = 98.0% [95.7, 99.1]** |
| paired difference, control - M1 | +0.3 pp [-0.7, +1.7] |

* (a) the control's rate (98.0%) is not above M1's upper bound (98.9%): **met**. The paired interval includes 0.
* (b) episodes with an invalid action: 1 of 300 (0.3%), limit 5%: **met**.
* **Verdict: control passes.** With shuffled rewards the gradient carries no task signal, so a result equal to M1 is what a working pipeline should give; an improvement would have meant the gains came from somewhere other than the reward.
* Also unchanged: the material spec error rate (`eval/spec_errors.py`) is 69/280 = 25% [20, 30] for the control against 72/280 = 26% [21, 31] for M1 (the two known spec bugs persist, as expected, since nothing trains them).
* All three spot-check dumps (steps 10, 20, 30) were clean, no STOP was needed (`reports/2026-11-21-control-attempt2/spotcheck-notes.md`).

## Measured cost (the figure the owner asked for)
**0.213 GPU-h per step** on one T4 (765 s per step on average over 30 steps, 727 s over the last 10; 6.38 GPU-h for the 30 steps). At that rate 60 steps would be 12.8 GPU-h (under the 15 GPU-h cap, but over Kaggle's 12-hour session limit). The main run therefore decodes 16 sequences per chunk instead of 8; the speed-up is **unverified** (an out-of-memory error now splits the chunk and retries).

Files: `judgement/judgement.json`, `grpo-control-q8/` (results.jsonl, episodes.jsonl, manifest), `run.log`, `server.log`.
