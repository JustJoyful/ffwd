# X1 re-graded with checker v1 (T2)

Original numbers are unchanged in the Phase 0 report. This is a **separate row**.

| Row | Success (Wilson 95%) |
|---|---|
| X1-deepseek-flash (original, checker v0) | 47/50 = 94% [84%, 98%] |
| X1-deepseek-flash **re-graded with checker v1** | 48/50 = 96% [87%, 99%] |

Method: checker v1 changes only the A/V-offset measurement, so only the 3 F11 tasks (s31-s33) were rerun live against DeepSeek
with checker v1 (cost $0.0012); the other 47 results are carried over from Phase 0.
Tasks that changed: ['s31-audio-half-second-behind'].

Caveats: (1) this is a rerun, not a pure re-score: in the original run DeepSeek's first command was the wrong direction and it
never finished; in the rerun its first command was the correct audio advance (`-itsoffset -0.5` on the audio input). The command
that the original run tried second (and v0 wrongly failed) is now covered by a golden case and passes. (2) Remaining X1 failures
(s13 rotation, a02 ambiguous) are unchanged. (3) Offsets made with filters (adelay/atrim) still cannot be verified from timestamps.
