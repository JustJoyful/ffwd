# Shuffled-reward control, attempt 1: CUDA out of memory at step 2 (21 Nov 2026)

**Failed, no checkpoint pushed** (the first is at step 10), so nothing to clean up. Kernel `justjoyful/ffmpeg-agent-grpo-auto` version 6, mode `control` (30 steps, shuffled rewards, pool of 358 prompts), started by the owner with Run All on a Kaggle T4 (one GPU, 14.56 GiB).

## What the log shows
* Setup and step 1 ran normally. Step 1 (from the pasted log): `step_time 410.9 s` (8m22s with warm-up), mean reward 0.963, reward std 0.323, `frac_reward_zero_std` 0.125 (12.5% of groups with no reward variance), completions of 169 to 686 tokens (mean 331), `clipped_ratio` 0, loss -0.0005, grad norm 0.13. **410.9 s per step on one GPU = 0.114 GPU-h per step** (a first measurement, with warm-up: about 3.4 GPU-h for 30 steps and 6.8 GPU-h for 60, against the 15 GPU-h cap).
* Step 2, during batched generation (`hf_batch.py` -> `model.generate` -> KV-cache update): `torch.OutOfMemoryError: Tried to allocate 118.00 MiB. GPU 0 has a total capacity of 14.56 GiB of which 2.81 MiB is free ... 10.20 GiB is allocated by PyTorch, and 4.20 GiB is reserved by PyTorch but unallocated`. Exit code 1.

## Cause and fix (commit `b832a9e`)
Each generation chunk was 32 sequences and `generate(..., output_scores=True)` keeps the full-vocabulary scores (about 152k values) of every new token of every sequence in the chunk, about 2.5 GB in fp16 for a chunk of 32 x 256 tokens, plus the KV cache. After step 1's training the allocator was fragmented (4.2 GiB reserved but unallocated), so the next batch did not fit. Fixes: chunk size 32 -> 8 (scores 4x smaller); `del out` and `torch.cuda.empty_cache()` after each chunk; `run_chunks` splits a chunk in half and retries on an OOM (a lone request that still fails raises), tested without torch (`tests/grpo/test_hf_batch_chunks.py`); `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` set in the kernel script (what the error message recommended). Not reproducible locally (a 6 GB GPU); the retry makes a repeat non-fatal, and the first steps of attempt 2 will show the real memory margin and the step time with the smaller chunks.

Kernel version 8 (control, saved without running) carries the allocator setting; `hf_batch.py` comes from `main` at run time.
