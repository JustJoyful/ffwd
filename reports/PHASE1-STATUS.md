# Phase 1 status (autonomous run; owner away from 16 Nov 2026)

Plan: `docs/superpowers/plans/2026-11-16-phase-1-core-model.md`. Rule while the owner is away: do every ungated task; **never cross an [ASK] gate**
(DeepSeek spend incl. paraphrases/teacher/X1, the main GRPO run + shuffled control, the single test run, publishing beyond private repos).
No questions to the owner; conservative defaults, documented. All work is on `main` (commits tagged by task).

## Done (code + tests, all ungated)
| Task | What |
|---|---|
| T1 | protocol 0.2.0, split-purpose guard (`training/taskgen/loader.py`): training code cannot read test splits |
| T2 | fail-closed bubblewrap sandbox option, rollout timeouts. **FFmpeg pin blocked on D-024** |
| T3 | corpus v1 (22 clips: VFR, 4:3, ProRes, MKV, mono/44k, noisy, known A/V offsets, rot270), tags, hash-verified Hub distribution code. **Hub push not done** (creates a repo on your account) |
| T4 | checker v1.3: quality floor (SSIM/PSNR) for size targets; 6 golden cases |
| T6 | D-026: ONE agent chat template (empty think on every assistant turn; stock Qwen3 drops it from history, which would skew train vs inference); spec-first prompt v1 (DRAFT hash until D-024); `require_spec` loop option. Verified identical in HF, Jinja and llama.cpp |
| T7-T10 | task generator v1: F1-F12 samplers on a shared plan, compositions of 2-4 families, ambiguous/unsupported tasks, 5 train + 2 held-out styles, content-hash splits, held-out family combos, executed-reference verification, parallel build + manifest |
| T11 | leakage audit (`eval/leakage.py`). **Train paraphrases via DeepSeek not run (gated)** |
| T12 | test-run lock (`eval/testlock.py`), Phase 1 preregistration as a DRAFT |
| T13 | teacher runner + data card (train-only, spec-first, passing-only, off-peak gate, refuses draft prompt). **Pilot/bulk gated** |
| T15 | rejection sampling code (free local model) |
| T16 | SFT dataset/mix/validation split, LoRA SFT trainer, build CLI (code only; not trained) |
| T17 | lockstep batched rollouts + HF batched generator (verified equal to one-at-a-time under padding) |
| T18/T19 | stop rules (`training/grpo/gates.py`), main GRPO driver (`training/grpo/main_run.py`); **never run: gated** |
| T22 | parity metrics (`eval/parity.py`); GGUF export needs llama.cpp's converter script (not fetched: external code) |
| T23 | `ffmpeg-agent` CLI + plain-language spec describer + goldens |
| T24/T25 | results report builder (Holm, denominators, test-lock checks), model/data card builders, licence audit |
| extra | D-032 proposal: free programmatic "oracle" trajectories (`training/teacher/oracle.py`) |

## Smoke tests run (local RTX 3050, free, tiny; NOT the gated runs)
- Task build v1 finished: 4486 train / 300 dev / 500 test-iid / 200 test-compositional / 200 test-phrasing (`reports/2026-11-16-taskgen-v1/`): held-out splits pass the leakage gate (max Jaccard 0.69 / 0.74 < 0.9). Limitations there (single-family content space is small; few ambiguous/unsupported dev tasks).
- Oracle trajectories: 60/60 train tasks solved through the real spec-first loop (draft prompt). SFT examples are ~1.6k tokens each (only ~220 trained): `SFT_MAX_LEN` raised to 3072; default batch 2 x 8.
- SFT: 3 steps on the local GPU ran (eval loss 0.705), adapter saved, merged model carries the agent template (`tests/export`).
- GRPO driver: 1 step, 2 generations x 2 prompts, real lockstep generation + telemetry + checkpoint: works (0.013 GPU-h; junk policy, as expected after 3 SFT steps).
- GGUF export: **blocked** on llama.cpp's `convert_hf_to_gguf.py` (not in the release binaries; fetching it means running external code). Wrapper is ready: set `LLAMA_CPP_DIR` / `LLAMA_QUANTIZE`.

## Kaggle kill-and-resume: failed at secrets (needs one UI step from you)
The pushed kernel `justjoyful/ffmpeg-agent-resume-auto` waited ~2 h in the GPU queue, then died after 1 s: `kaggle_secrets.get_secret('HF_TOKEN')` -> HTTP 400.
Kernels pushed from the CLI have no secrets attached, and I will not embed tokens in pushed code. **Owner step:** open https://www.kaggle.com/code/justjoyful/ffmpeg-agent-resume-auto -> Add-ons -> Secrets -> tick `HF_TOKEN` and `GITHUB_TOKEN`. Then either re-run
`uv run python -m training.grpo.kaggle_kernel push --mode train` (I can do this on the next wakeup once told) or click Save & Run. The log is in `reports/2026-11-16-phase1-dev-baselines/kaggle-session1-error.log`. D-022's Kaggle verification stays open.

## Waiting on the owner
1. **G0:** Kaggle kill-and-resume result (kernel `justjoyful/ffmpeg-agent-resume-auto` still QUEUED), D-024 FFmpeg pin decision, D-025-D-031 proposals in the plan, D-032, your ~20 new spike-v1 tasks + 2-3 clips.
2. **G-terms:** read DeepSeek's terms (training on outputs) and send the off-peak window (`config.DEEPSEEK_OFFPEAK_UTC`, `TEACHER_TERMS_URL`).
3. **G1/G2:** approve the teacher pilot (<= $0.05) then bulk (<= $2.30); approve the paraphrase spend (<= $0.30).
4. **G3:** approve the shuffled-reward control and the main GRPO run (<= 15 GPU-h).
5. **G4:** preregistration FINAL + the single test run. Your ~10 own clips + ~100 test-real requests.
6. Freeze prompt v1 (set `SYSTEM_PROMPT_V1_SHA256`) after D-024.

## Not done / blocked
- Real SFT, M1, GRPO: need data (gated) and a GPU (Kaggle queued; local RTX 3050 is for smoke tests only).
- B0 v2 (patterns from train phrasing only) and dev baselines on the new splits.
- Dual-runtime (ffmpeg.wasm) conformance run: Phase 2.


## Kaggle retry after owner attached secrets (22:20 IST)
Pushed `--mode train` as kernel version 2. It failed the same way: `get_secret('HF_TOKEN')` -> HTTP 400 (`reports/2026-11-16-phase1-dev-baselines/kaggle-session2-error.log`). Secrets attached in the UI are not reaching API-pushed runs. Not re-pushed again. Next step needs the owner: in the kernel's UI (Add-ons > Secrets) tick the HF_TOKEN toggle for the latest version and run it from the UI, or tell me to use another method.


## Dev baselines on dev v1 (n=300), finished 23:08 IST
B0 regex 158/300 = 53% [47%, 58%]; B2 stock Qwen3-0.6B 0/300 = 0% (all 8 turns invalid: writes `{"spec":...}` without `"action"`). Details and Wilson tables by difficulty: `reports/2026-11-16-phase1-dev-baselines/summary.md`.


## Kaggle kill-and-resume: PASSED on the Hub evidence (23:56 IST)
Owner ran session 1 (checkpoints 2, 4 on `JustJoyful/ffmpeg-agent-ckpt`), then re-ran with `MODE='resume'` (after the clone fix + clearing `/kaggle/working/ckpt`). `checkpoint-6` and `-8` appeared; in `checkpoint-8` the `log_history` and `toy_metrics.jsonl` steps 1-4 are identical to `checkpoint-4`, steps 5-8 continue, LR 6.25e-06 -> 5e-06 across the boundary. Recorded in D-022. Still unconfirmed: the notebook's `verify_resume` line (`"ok": true`) and that local ckpt was empty; owner can paste the log tail to close both.


### Kaggle resume: `verify_resume` confirmed (17 Nov)
Owner pasted the console output: `"ok": true`, `"problems": []`, `"steps": [1,2,3,4,5,6,7,8]`, exit code 0. Kill-and-resume is closed (D-022 updated). Only the "local ckpt dir was empty" detail rests on the notebook edit rather than a log line.


## Owner plan review applied (17 Nov, after the Kaggle test)
Done: D-027 (change a: held-out style `technical` -> `context_first`; change b: real clips split by clip, `add_clip --role` required, CI test with a planted violation), D-028 to D-031 recorded as approved, D-024 marked accepted (option A) from the D-029 wording, preregistration edits (Q7 = one pooled comparison on test-real + test-phrasing, per-family descriptive only; detectable-difference table; M1 >= 90% "SFT nearly sufficient" rule; kept-rate gate rule proposed, number set after the X1 dev run), plan edits (G0a blocks T16+ only, T4 Step 4 reworded, status table), `PHASES.md` and `CLAUDE.md` set to in progress. `reports/TEST_RUNS.jsonl` does not exist: no test split has ever been run, so changing test-phrasing wording invalidates nothing.

**Blocked, needs the owner (D-024/D-029 pin):** I downloaded the 5.1.1 static build (sha256 `2d848c37...9f42`, `~/.cache/ffmpeg-pin-dl/ffmpeg-5.1.1-amd64-static.tar.xz`) but the sandbox classifier denied extracting and running it, as last time. Please run in this session: `! cd ~/.cache/ffmpeg-pin-dl && mkdir -p x && tar -xf ffmpeg-5.1.1-amd64-static.tar.xz -C x && x/ffmpeg-5.1.1-amd64-static/ffmpeg -version | head -1`. If runs of that binary are still refused for me, add a Bash permission rule for it. Until then: no pin enforcement, no split rebuild (the test-phrasing file still holds the old `technical` wording; it is rebuilt once, together with the pin, to avoid regenerating twice), `LOSSLESS_ROTATE_SPELLING` unchanged.

**Still waiting on the owner:** D-032 decision (text pasted in the reply), DeepSeek terms snapshot + off-peak window (nothing paid runs until the terms file exists), at least 10 own clips with `--role`, about 100 test-real requests.
