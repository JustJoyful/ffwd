# Kaggle smoke run through the kernel (20 Nov 2026)

**Result: passes.** The 2-step `main_run` ran on a Kaggle T4 (fp16, one GPU) from a script kernel (`justjoyful/ffmpeg-agent-grpo-auto`, version 2, `PARAMS mode=smoke`), reached `RUN DONE: mode=smoke` with exit code 0, and pushed a complete checkpoint to the Hub after each step. A pipeline test only: train tasks (T18 sample table), tiny settings (2 generations, 1 prompt per step, 128 new tokens, 2 runs), throwaway private repo `JustJoyful/ffmpeg-agent-ckpt-smoke-kaggle` (removed after this report). No test split was read or present.

## Evidence (G3 criterion d)
From the log lines the owner pasted (`evidence-pasted-by-owner.txt`; the full log stayed in the web-UI session):
* `ffmpeg pin: sha256 2d848c37...29f42 == pinned (5.1.1-static): OK` and `ffmpeg pinned build verified: 5.1.1-static (pinned 5.1.1-static)`
* `checkpoint-1 pushed to ...` and `checkpoint-2 pushed to ...`; the Hub repo (private) held both checkpoints with adapter, optimizer-side state (`scaler.pt` proves the fp16 GradScaler path ran), tokenizer, `metrics.jsonl`, `telemetry.jsonl`, `trainer_state.json`, `pass_rates.json`.
* The held-out-data assertion ran before anything else and the run continued, so it passed; its `ASSERT OK` line was not in the evidence file because the assertion printed to the console only (fixed in `kaggle_remote.py`: it is now also appended to `run.log`).

## Secrets and the API
* The probe run in the web-UI editor saw both Secrets (`ok`). The same script pushed through the Kaggle API (version 2) did NOT: `get_secret` raised `ConnectionError`. This smoke was therefore started by the owner with Run All in the editor. Whether a Save Version from the UI makes later API-pushed versions see the Secrets is being tested (see D-044).

## Observation: step 1 of the smoke
`metrics.jsonl`/`telemetry.jsonl`: step 1 mean reward -1.75, invalid-action rate 67%, pass 0; step 2 mean reward 1.075, pass 1. n = 2 rollouts per step, so not a measurement. The smoke caps each action at 128 new tokens (the real run uses 256), which can truncate a spec JSON into an invalid action; the stop rule "rising invalid-action rate" stays active in the real run, and the first control steps should be read for it. Step time on the T4: 98.9 s for step 1 (includes warm-up), 30.5 s for step 2 (0.0085 GPU-h).

Files: `evidence-pasted-by-owner.txt`, `metrics.jsonl`, `telemetry.jsonl`, `trainer_state.json` (from `checkpoint-2` on the Hub).
