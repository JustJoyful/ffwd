# Rule for the shipped native format, written BEFORE the Q4_K_M run (22 Nov 2026, A3)

Question: ship M3 as Q8_0 (640 MB) or Q4_K_M (397 MB)? Dev only; the 100 tasks are the same seeded sample as the M1 parity (`random.Random(20261115).sample(sorted dev ids, 100)`, `eval/hf_parity.sample_ids`); the Q8_0 side is the already published dev run `reports/2026-11-22-m3-ckpt60-dev/grpo-m3-ckpt60-q8` restricted to those ids (not re-run). Same prompt, template, harness and run budget; greedy.

**Q4_K_M ships only if ALL of these hold** (otherwise Q8_0 ships):
1. Success on the 100 tasks is within 2 percentage points of Q8_0 (Q4 - Q8 >= -2 pp), and exact McNemar p > 0.05.
2. No increase in invalid-action episodes beyond 2 more than Q8_0 on the sample.
3. Mean runs per graded task is not more than 0.05 above Q8_0 on the sample.
4. Needless-or-fail on the copy-eligible tasks of the sample (Q3a definition) is not higher than Q8_0's.

Why these: 100 near-saturated tasks cannot show equality, only rule out a large loss (the same limit as `reports/2026-11-20-m1-parity`); so the bar is "no visible loss on success, format validity and the two efficiency measures M3 was trained for", and a tie goes to the larger, safer format. Q4_K_M's benefit is download size (and speed, measured separately), not accuracy. This is a dev decision about packaging; it changes nothing in the Phase 1 test run, which uses the frozen Q8_0 models (Amendment 3, item 7).
