# Phase 1: known bugs and honest limitations

Read with `summary.md` (results and the preregistered tests), `failure_taxonomy.md` and `telemetry.md`. Everything here is a reading of results that were already fixed; nothing was changed after the test run.

## What the results do and do not show

- **Q2 and Q7 hold.** M1 beats the untrained baseline B2 on test-iid (+97.0 pp), and M3 beats the regex baseline B0 on test-phrasing (+29.5 pp).
- **Q3a holds, Q3b does not.** M3 has fewer needless-or-failed re-encodes than M1 (-11.1 pp, n = 90, the tasks where a stream copy was possible), but the runs-per-task difference on test-iid is -0.024 [-0.061, +0.011], p = 0.198: **not rejected**. By the preregistered rule the sequence stops there, so Q4 (M3 vs the DeepSeek teacher) is descriptive only: +0.4 pp [-1.6, +2.4]. We do not claim M3 matches the teacher; the interval is compatible with a small gap either way.
- **The efficiency claim rests on Q3a alone** (a small subset, n = 90, one training seed) plus the guard (M3 - M1 success +0.11 pp, one-sided lower bound -0.89 pp against -2.0 pp: met). It is a real but narrow result.
- **M1 and M3 are level on success** (866/900 vs 867/900 on the generated splits). GRPO did not raise accuracy here; what it changed is the re-encode rate on lossless-eligible tasks (9% to 2% on test-iid).
- **One training seed per system.** Differences between M1 and M3 are one run each; the intervals cover test-set sampling noise only, not training-run variance.

## Baselines

- **B2 (stock Qwen3-0.6B + the loop) scores 0 of 900.** This is real model behaviour, not a harness fault: it packs several actions into one reply, runs away generating text, never produces a valid `run`, and every episode ends at the turn budget with 8 invalid turns. B2 is a floor: it shows the loop alone does not make a stock 0.6B model work.
- **B0 (frozen regex)** replies `unsupported` on 331 of the 834 supported tasks (40%): a transparent floor for what rules alone cover.

## Metric caveats

- **Material spec error rate is high even where success is high** (M3 22% on test-iid, against 97% success). The check runs against the spec the model itself states, so a wrong-but-consistent spec can pass; this metric exists to expose that, and is descriptive only (not preregistered).
- **Two known systematic M1 spec bugs carry into M3** (recorded at D-043): width and height not swapped after a rotation (35% of rotate tasks on dev vs 7% elsewhere), and `end_s` stated as source time after a speed change (51% vs 3%). A data fix is a post-Phase-1 item.
- **test-iid has near-duplicate requests of training requests** (the leakage audit, `reports/2026-11-22-leakage-audit`). The report shows the full split and the deduplicated subset side by side; the dedup numbers are descriptive and close to the full-split ones.
- **The success rate on generated tasks is not the success rate on real clips.** Generated splits use the 22-clip corpus. The owner-recorded `test-real` set is a Phase 4 addendum and has not been run.

## Deployment risk carried into Phase 2

- **Quantisation is not free.** M3 at Q8_0 scores 97/100 on the dev parity sample, M3 at Q4_K_M scores 60/100 (`reports/2026-11-22-m3-q4km-parity`). Q8_0 ships. The browser runtime plans a 4-bit MLC build (q4f16_1); **that conversion has not been tested**, so the browser model may be materially worse than these numbers until it passes the same parity check on the same dev sample.
- **Browser FFmpeg is 5.1.4 (ffmpeg.wasm core-mt), the evaluation pin is 5.1.1.** The suite and conformance cases pass on 5.1.1; a behavioural gap is expected to be small but is unmeasured.

## Sanity controls (all done before the test run)

Checker mutation self-test killed 411 of 413 mutants (the 2 survivors are inside the checker's tolerance); leakage audit on the final splits; Q8_0 vs Q4_K_M parity. The human review of 50 passed M3 outputs (`reports/2026-11-23-passed-review`) was **generated after seeing the results and is pending the owner's verdicts**; its outcome will be added here as an addendum, not edited into the numbers above.

## Cost

DeepSeek spend on the test run (X1): $0.5985 against the $0.70 cap, within the $4 lifetime cap.
