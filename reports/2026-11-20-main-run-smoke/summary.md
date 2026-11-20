# 2-step main_run smoke test and the Kaggle web-UI notebook (20 Nov 2026)

**Result: the smoke run passes end to end locally; the first attempt found a bug that would have killed the real Kaggle run at its first Hub push. The notebook is ready for you to run; it has not been run on Kaggle.**

This is a pipeline test only. The 2 steps are tiny (2 generations, 1 prompt, 128 new tokens, 9 in-band train tasks from the T18 sample), the checkpoints went to a throwaway private repo, and nothing from it is a training result or will be selected, evaluated or used. Train tasks only; no test split read; no money.

## What was run

`training.grpo.main_run` (the real GRPO driver) on the local RTX 3050 6 GB: `--init data/models/m1-merged/...`, `--steps 2 --save-steps 1 --num-generations 2 --prompts-per-step 1 --max-new-tokens 128 --max-runs 2 --pass-rates <T18 table> --pass-rates-subset --hub-repo JustJoyful/ffmpeg-agent-ckpt-smoke`. Log: `smoke.log`; exit 0.

Evidence lines in the log (what criterion (d) asks for):
```
ffmpeg pinned build verified: 5.1.1-static (pinned 5.1.1-static)
checkpoint-1 pushed to JustJoyful/ffmpeg-agent-ckpt-smoke
checkpoint-2 pushed to JustJoyful/ffmpeg-agent-ckpt-smoke
```
The Hub repo (private) holds `checkpoints/checkpoint-1` and `checkpoint-2` (adapter, optimizer/scheduler state, tokenizer, metrics, telemetry, the pass-rate table).

## Bugs found and fixed by the smoke run (all would have hit the Kaggle run)

1. **Hub push rejected the checkpoint** (`smoke-attempt1-readme-metadata-error.log`): PEFT writes a `README.md` into each checkpoint whose `base_model` is the local `--init` path, and the Hub refuses it as invalid metadata. On Kaggle `--init` is also a local path, so the first push (step 10) would have failed. Fix: `HubRemote.push` skips `README.md` (`ignore_patterns`); pinned in `tests/grpo/test_ckpt_sync.py`.
2. **A partial pass-rate table crashed the filter** (`KeyError` on the first unmeasured task). Every table we have is partial (T18 sample 302; pilots 300 + 300) and the scale-up was rejected. Fix: an explicit opt-in `--pass-rates-subset` (`select_tasks(..., subset=True)`): unmeasured tasks are EXCLUDED, never assumed in band. The default stays strict. Test added.
3. **No log evidence of the pin check or of Hub pushes.** `ffmpeg_pin install` verified the sha256 silently; checkpoint pushes printed nothing. Now: `install()` prints `ffmpeg pin: sha256 <hash> == pinned (...): OK`; `main_run` calls `require_pinned()` at startup (fails closed on any other FFmpeg) and prints the version; `SyncCallback` prints `checkpoint-N pushed to <repo>` after every push.

## The notebook: `training/grpo/kaggle_main_run.ipynb`

Run it in the Kaggle web UI (API-pushed kernels cannot read Secrets). Settings: GPU T4, Internet on, Secrets `GITHUB_TOKEN` (read-only) and `HF_TOKEN` (write) with this notebook's checkbox ticked. Tokens come only from the Secrets; the clone's remote URL is reset so no token stays in `.git/config`.

| cell | does |
|---|---|
| 2 | parameters (repos, `GRPO_APPROVED = False`, `PASS_RATES_MAIN = None`) |
| 3 | clone `main`, install uv + `uv sync --group train`, `ffmpeg_pin install` (sha256 check, logged), `ffmpeg_pin check`, CUDA check |
| 4 | rebuild M1's init: adapter from the private Hub repo + public Qwen3-0.6B, merged in fp16 (**verified locally to give a byte-identical `model.safetensors`** to the evaluated model) |
| 5 | the 2-step smoke, checkpoint pushed after every step |
| 6 | evidence: greps the pin and push lines from `run.log` into `evidence.txt` and lists the checkpoints on the Hub |
| 7, 8 | main run (100 steps, group 8, 8 prompts/step, 15 GPU-h cap, push every 10) and resume: **refuse to run** unless you set `GRPO_APPROVED = True` and choose the task set (`PASS_RATES_MAIN`) |

Checked locally: every cell compiles, shell lines use only `{NAME}` variables, the Hub corpus pulls and hash-verifies (36 clips), the M1 rebuild matches. Not checked: the notebook on Kaggle itself (uv install, T4 fp16 precision path, the Secrets API in the web UI).

## Things to know

* **Test-real clips are not in the Hub corpus** (`push_corpus` excludes role `test-real`), so the Kaggle machine never holds them. The cloned repo does contain the task files of all splits (tracked in git, hash-pinned); the loader refuses to read test splits for training (tests green), but if you would rather the Kaggle clone not contain them at all, say so and I will move the test-split task files out of git.
* **The main cell cannot yet use the pilot tasks:** `main_run` loads the standard train file only, so the widened and recovery pilot tasks (and recovery openings, whose rollout support is not built) are not trainable yet. With the T18 table alone only 9 train tasks are in band. Which task set to train on is the open decision in D-040.
* In the smoke telemetry both samples passed in both steps, yet the group reward still varied (std 0.012 and 0.05): the variance came from `spec_acc` (0.76 and 0.60 mean) and efficiency. That is the same pattern as in `reports/2026-11-20-reward-variance`.
* Smoke speed on the local 6 GB GPU: about 15 s per step with these tiny settings (0.0042 GPU-h/step); not comparable to Kaggle full settings (Phase 0 toy: 0.071 GPU-h/step).
* Left on disk: three small smoke checkpoint dirs `~/.cache/ffagent-main-smoke-*` (two from the failed attempts); safe to delete.

Files: `smoke.log`, `smoke-attempt1-readme-metadata-error.log`, `metrics.jsonl`, `telemetry.jsonl`, `pass_rates.json`.
