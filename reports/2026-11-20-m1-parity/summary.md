# M1 parity: HF fp16 vs GGUF Q8_0 (20 Nov 2026)

Dev only. 100 dev tasks drawn by seed (`random.Random(20261115).sample(sorted ids, 100)`), not by outcome. The GGUF side is the already published dev run (`reports/2026-11-20-m1-dev/M1-0.6b-q8`, not re-run); the HF side is the merged fp16 model the GGUF was made from, greedy, same agent chat template, same prompt v1, same harness and run budget (`eval/hf_parity.py`, `eval/hf_policy.py`). Wilson 95% intervals; paired bootstrap 10,000 resamples.

| | success | 
|---|---|
| GGUF Q8_0 (a) | 98/100 = 98% [93%, 99%] |
| HF fp16 (b) | 99/100 = 99% [95%, 100%] |

* **Agreement 99/100.** Discordant pairs: GGUF-only passes 0, HF-only passes 1. Exact McNemar p = 1.0. Paired difference HF - GGUF = +1.0 pp, 95% CI [0.0, +3.0].
* The single discordant task is `dv-958fbe818c-terse` (F2+F9, join then remove sound), one of the 7 dev failures of M1 GGUF: HF fp16 solved it, GGUF hit the run limit. With the join+remove-audio weakness (see the failure analysis) that is a coin-flip-sized difference, not evidence of a quantisation loss.
* HF side: 0 invalid turns, 0 errored episodes.

## Text agreement (success can agree while the text differs)

* First assistant turn byte-identical on **86/100** tasks; the whole sequence of assistant turns on **65/100**.
* Of the 35 tasks whose transcripts differ: 14 differ only in the free-text `note` of the final `finish` action; 14 differ in the first-turn spec in fields that the gold spec leaves unconstrained or at a different tolerance (for example `fps` 30 vs 37.5, `tolerance_s` 0.1 vs 0.2, `end_s` 2 vs 4.0), and the run still passes; 6 differ in the first run command; 1 differs in the number of turns. None of the differences changed the outcome except the discordant task above.

## What this does and does not show

* With both formats at 98-99% on this sample, 100 tasks can only rule out a large quantisation loss (a drop of more than roughly 3 pp is excluded at the interval's edge). It cannot show Q8_0 is exactly lossless, and does not claim it. The transcript-level numbers say they are not bit-identical models in behaviour, only equivalent in outcome here.
* Dev, in-distribution tasks only. The test-split behaviour of Q8_0 vs fp16 is not measured and is not run.
* Not covered: the Q4_K_M path, and the browser (MLC q4f16_1) parity, which belongs to Phase 2.

Spend $0. HF run took 12 minutes on the RTX 3050 6 GB. Hashes, commit and the sampled ids (`run/parity.json: sample_ids`) are in `manifest.json` and `run/`.
