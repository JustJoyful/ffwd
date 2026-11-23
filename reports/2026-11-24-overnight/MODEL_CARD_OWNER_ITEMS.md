# Model card and data card: the items only you can decide (24 Nov 2026)

Everything in `docs/hf-cards/model-card-m3.md` that is not a decision is filled (tonight: the quantisation and browser results, the shipping format, the MLC finding, the file hashes). What is left are the `TODO(owner)` items below, each with suggested text to confirm or change. Nothing here is pushed anywhere; both cards are for PRIVATE repos only until the DeepSeek terms are reviewed.

## Model card (`docs/hf-cards/model-card-m3.md`, 5 distinct items)
1. **Repo id.** The repo still uses `ffmpeg-agent-*` names until the planned ffwd rename (D-046). Suggestion: `JustJoyful/ffwd-0.6b` (model, with the Q5_K_M GGUF as the main file). Do this together with the planned rename and redirects.
2. **Weights licence** (front matter and Licence section). The repo only records "compatible with the base model licence, verify at release" (D-016). Suggestion: use the base model's licence for the weights. I did not re-check the Qwen3-0.6B licence tonight: read it on the base model's Hugging Face page and quote it. This also depends on the DeepSeek terms review (the training data includes DeepSeek outputs). Project code stays GPL-3.0 (D-016).
3. **Repo link** to put in "How to run". Suggestion: leave the private GitHub name out until the repos are public or renamed, and write "project code: GPL-3.0, link added at release".
4. **Seeds actually used.** From the code: the SFT default seed is `config.TASKGEN_SEED` (20261116) unless the Kaggle runner passed `--seed` (it has no such argument in what I read); the GRPO main run passes no shuffle seed; the bootstrap/server seed is 20261115. I could not confirm what the Kaggle runs received. Suggestion: write "SFT seed 20261116 (code default); GRPO single run, trainer-default sampling seeds; evaluation seed 20261115" only if the Kaggle logs agree; otherwise keep "single seed" and drop the numbers.
5. **LoRA adapter of checkpoint-60** (private repo `JustJoyful/ffmpeg-agent-ckpt-grpo`): upload it next to the GGUF or not. Suggestion: yes, as for M1 (it lets others re-merge and re-quantise), unless the DeepSeek review says otherwise.

## Data card (`docs/hf-cards/data-card-corpus-and-tasks.md`, 6 distinct items)
6. **Repo ids and what is uploaded** (the task splits and teacher trajectories are not on the Hub). Suggestion: corpus clips with licences (already private on the Hub), the task generator, and the task files with hashes only for the test splits; NO teacher trajectories until item 8.
7. **Dataset licence.** The clips keep their own licences. Suggestion: the generated tasks and manifests under CC0 or CC BY 4.0 (your choice); trajectories not licensed until item 8.
8. **DeepSeek terms review outcome and whether trajectories may be uploaded at all.** Record the outcome and date. Suggestion: until it is done, say "trajectories are local only".
9. **Date you verified the CC BY 3.0 licence** for Tears of Steel and for the Wikimedia Commons Big Buck Bunny 4K file. Suggestion: check both pages, then write the date and the URLs you checked.
10. **`train/hard-v1.jsonl` (300 tasks) is not in MANIFEST.json.** Suggestion: either add it to the manifest with its generator version and seed (the file hash `e3cb68be...` is already recorded), or state in the card that it is an extra train set outside the pinned manifest.
11. **Clip counts quoted elsewhere** (the M1 hub README says "14 real CC-licensed clips"; the Phase 1 LIMITATIONS said "22-clip corpus", now corrected). The current manifest has 22 synthetic plus 13 CC BY 3.0 clips visible to task generation (35). Suggestion: quote 35 everywhere and fix the M1 hub README.

## Before any of it goes public (see the launch checklist in `MORNING_REPORT.md`)
DeepSeek terms review done and recorded; a contents check of each repo (no test-real clips, no trajectories unless cleared, hashes match); licences of every clip, model and dataset recorded; then and only then change visibility.
