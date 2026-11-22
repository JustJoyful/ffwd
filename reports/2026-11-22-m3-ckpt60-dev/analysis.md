# M3 = checkpoint-60 on dev (22 Nov 2026), informational

Dev only; greedy, same server args and prompt as M1, the control and checkpoint-50. M3 was fixed as the last clean checkpoint of the run before any dev result (D-045); nothing here changes the selection. `summary.md` has the tables.

| | success | mean runs (289 supported tasks) | episodes with an invalid turn | ends by run budget | material spec error rate |
|---|---|---|---|---|---|
| M1 | 293/300 = 97.7% | 1.135 | 0 | 7 | 72/280 = 26% |
| control (shuffled reward) | 294/300 = 98.0% | 1.111 | 1 | 5 | 69/280 = 25% |
| checkpoint-50 | 290/300 = 96.7% | 1.149 | 0 | 10 | 68/280 = 24% |
| **checkpoint-60 (M3)** | **291/300 = 97.0%** | **1.149** | 1 | 9 | 68/280 = 24% [20%, 30%] |

* **Paired against M1:** M3 lost 3 tasks M1 passed and won 1 (net -2, -0.7 pp; far from significant at n = 300). The three losses end by the run budget (4 runs) where M1 needed 1 to 3: `dv-a2d9bf9515-polit`, `dv-cb5887d1ae-polit`, `dv-ee373c6c75-sympt`. Checkpoint-50 lost the same three plus `dv-5890de054d-polit`, which checkpoint-60 recovers; the one win (`dv-12ea3f96c9-terse`) is the same in both.
* **Efficiency did not transfer to dev:** paired mean-runs difference against M1 +0.014 (SE 0.022); run-budget endings 9 against M1's 7 (the control: 5). The training gain was on the hard pool, and the last 15 steps revisit prompts it already trained on (see the notes of the run); dev, which was never trained on, shows none.
* **What the retries look like (two episodes read, not a study):** `dv-ee373c6c75-sympt` (remove the audio and rotate): M1 does it in one run (`-c copy -an -metadata:s:v:0 rotate=270`); M3's first run leaves out `-an`, and its next runs try `rotate=180`, `rotate=90`, `rotate=90 -an` until the budget ends. `dv-cb5887d1ae-polit` (a 240 px wide GIF): M1 one run; M3 tries a palette filter graph, then plain `fps=10,scale=-2:240`, then adds `-q:v 2`, `-q:a 2` (irrelevant flags) until the budget ends. The model changes details between attempts rather than diagnosing the failed check, and drops a requested detail (`-an`, the width in the spec) in the first attempt. This is a hypothesis about a mechanism, not a finding.
* **Why training does not punish it:** passing on the 4th run still earns pass 1.0 plus 0.1 x 1/4 efficiency (1.025), against 1.1 for a first-run pass: 0.075 apart, so the reward is mostly about passing at all.
* **Spec errors:** unchanged within the intervals (width/height and end_s bugs untouched: spec_acc weight 0, D-043).
* **For the preregistration:** dev says M3 is not better than M1 on ordinary tasks and may be slightly worse on success. The guard (non-inferior within 2 pp, pooled over the three generated test splits, n = 900) is therefore a real test, not a formality: the dev point estimate is -0.7 pp. Efficiency endpoints (Q3a, Q3b) may come out null. This is recorded before the test run.
