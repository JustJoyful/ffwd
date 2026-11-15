# Baseline notes (read with baselines.md)

Primary comparison (preregistered): X1 − B2(Qwen3-0.6B) = **+94.0 pts [+86, +100]**; X1 − B2(1.7B) = **+86.0 [+76, +94]**.
GO threshold (≥ 25 pts) is met; RETHINK (best B2 ≥ 85%) is not. The browser half of the Phase 0 exit
criterion (F1/F4/F7 loop on real hardware) is still pending.

## Caveats found while reading the transcripts
- **Base models copy the system-prompt examples.** 0.6B reproduces the `spec` example verbatim (2–5 s trim)
  and drops a closing brace, so 0/50 actions parse. 1.7B copies example values (`{in:clip}`, the 2–5 s trim),
  gets rejected, then gives up with `unsupported` (45/50 episodes in B1). Its 3/3 "unsupported" successes come
  from refusing almost everything, not from recognising out-of-scope requests.
- **B1 = B2** for both sizes: the loop never helps because almost no base-model `run` reaches FFmpeg.
- **One X1 failure is likely a checker false negative.** `s31` ("audio half a second behind"): DeepSeek's 2nd–3rd
  runs used `-itsoffset -0.5` on the audio input, a valid fix, but checker v0 measures offset from stream start
  times, where negative shifts collapse to 0 (limitation declared in PREREGISTRATION.md). Scores are NOT
  re-graded post hoc; checker v1 must measure offset another way.
- **`a02` (ambiguous "make it smaller")**: DeepSeek compressed instead of asking; genuine failure.
- **4 X1 transcripts lost** (`s12`–`s15`, incl. failed `s13`) when the pilot was OOM-killed: results were flushed per
  task, transcripts were not (fixed in eval/run_baseline.py). Scores are complete.

## Cost and runtime
- DeepSeek: $0.0281 for 50 tasks ($0.00056/task, billed at peak rates; cache hit 76% in the pilot).
- Local runs: llama.cpp b12032 Vulkan on RTX 3050 6 GB, `--cache-ram 0` (the default 8 GB host prompt cache
  OOM-killed the desktop twice); whole chain 10 min, memory peak 2.6 GB inside a 4 GB systemd cap
  (eval/run_phase0_baselines.sh).
