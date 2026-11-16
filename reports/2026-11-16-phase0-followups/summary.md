# Phase 0 follow-ups: summary (16 Nov 2026)

The Phase 0 verdict stays **GO**; the Phase 0 report is untouched. Everything below is dev-split only.

## What changed
- **T1 CIs:** single rates use Wilson intervals (D-021). 0/50 is now [0%, 7%] (was "0-0%"). Tests compare against scipy.
  `baselines-wilson.md` (Phase 0 rows) and `baselines-all.md` (all rows) are regenerated; originals unchanged.
- **T2 checker v1:** root cause of the X1 `s31` miss: MP4 hides a negative audio offset behind an edit list and ffprobe clamps
  `start_time` to 0 (first audio packet pts is really -0.521 s). Offset is now measured from first-packet timestamps; tolerance
  unchanged (40 ms). 8 golden cases (`conformance/checker-offset.jsonl`) incl. wrong direction, unchanged file, 550 ms miss.
  **X1 re-graded with checker v1: 48/50 = 96% [87%, 99%]** (was 47/50); F11 tasks rerun live for $0.0012, see `x1-regraded-checker-v1.md`.
- **T3 harness:** the `-threads 4` cap lives in `harness-args.ts` and applies to every ffmpeg.wasm call (the big-file memory test had none).
  Browser probe parses `ffmpeg -i`: 29 ms vs ffprobe 30 ms, and a later `-i` probe breaks after ffprobe (core reload ~1.08 s). Matches the Python probe on all 12 clips.
- **T4 baselines (n = 50, dev):**

| System | Success (Wilson 95%) |
|---|---|
| B0 regex/preset | 92% [81%, 97%] (single-step 34/34, multi-step 9/10) |
| Qwen3-0.6B original / fair | 0% / 0% [0%, 7%] |
| Qwen3-1.7B original / fair | 8% / 8% [3%, 19%] |
| DeepSeek X1 (original / checker v1) | 94% / 96% |

  X1 - B0 = +2 pts [-6, +12]. **B0 is optimistic** (regexes written by the author of the tasks) and shows the 50 tasks are too
  template-like to separate presets from models; phrasing-diverse splits are needed for EVALUATION Q7. "Fair" prompt + schema-constrained
  decoding removed unparseable output but not the gap: replies are valid JSON with args that break the `{in:}`/`{out:}`/one-string-per-arg grammar
  (taxonomy in `baselines-all.md`, notes in `T4-notes.md`).
- **T5 checkpoints (D-022):** every save is pushed to a private HF repo; resume takes the newer of local/remote. Local rehearsal
  (SIGKILL, fresh dir, resume from remote) passes: steps 1-6, LR schedule continuous. Real HF push/restore smoke-tested.
  The 0.071 GPU-h/step figure applies to **Qwen3-0.6B** (LoRA r16, 16 rollouts/step, fp16, HF generate).
- **T6 (code only):** pass-rate filter (band 20-80%, K=8, train/toy splits only), reward v1 draft terms (ARCHITECTURE weights, in config),
  per-step telemetry (no-signal-group share, mean reward, term breakdown, invalid-action rate, over-ask/over-refuse, top-reward spot-checks every 10 steps),
  shuffled-reward control. Note: no reward-hacking telemetry existed in code before; these implement the ARCHITECTURE §7.4 guards. The size-target quality floor needs checker v1+SSIM (not done).
- **T7 bench:** load split (download/weights/shader/init), HEVC 1080p/4K, 100/500 MB inputs, F4, adapter info; crash-safe results; GPU policy flag defaults to warn (D-023, provisional); native bench with the same commands.

## Desktop bench numbers (RTX 3050 laptop, headed Chromium 159; native = this CPU)
| Job | Browser | Native |
|---|---|---|
| HEVC 1080p 60 s (92 MB) -> H.264 | 47.8 s | 6.0 s (~8x) |
| F4 480p, 100 MB H.264 input | 9.0 s | 2.3 s |
| F4 480p, 500 MB H.264 input | 8.5 s, tab survived | 3.8 s |
| HEVC 4K 60 s (228 MB) -> H.264 | **failed in 0.7 s** (exit -1; consistent with wasm out-of-memory, not confirmed) | 21.2 s |
| Model load cold (Qwen3-0.6B, 353 MB) | 40.4 s: download 33.7 s, weights 0.7 s, shader ~0 (not reported separately), init 6.1 s | |
| Model load warm | 1.2 s | |
| Decode | ~79 tok/s | |
Caveat: `measureUserAgentSpecificMemory` returns implausible numbers here (up to 36 GB), so peak memory is NOT usable; read OS-level peak RSS manually.
Implication: browser mode cannot yet be promised for 4K HEVC (route to helper) and 500 MB files work for re-encode-to-480p but only one data point.

## Still open (owner)
1. Kaggle kill-and-resume run + the 1.7B GPU-h/step (`training/grpo/kaggle_resume_test.ipynb`; needs the `HF_TOKEN` write secret).
2. Run the bench on 1-2 other machines incl. an iGPU-only laptop (`bench/README.md`); the iGPU policy stays "warn" (provisional) until then.
3. Review the 50 tasks (edits make `spike-v1`).
4. [ASK] Proposed, not started: paraphrase the dev tasks with DeepSeek (~$0.01) to measure B0/X1 on unseen phrasing. Not teacher-data generation, but it spends DeepSeek budget, so I'm asking.
