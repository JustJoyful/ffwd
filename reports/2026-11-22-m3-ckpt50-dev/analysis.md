# checkpoint-50 on dev (22 Nov 2026), informational

Dev only; greedy, same server args and prompt as M1 and the control. Per the rule fixed in D-045, M3 is the last clean checkpoint, so this is not a selection: M3 is checkpoint-60 if the resume finishes, otherwise this checkpoint. `summary.md` has the tables (made by `eval.dev_summary`).

| | success | mean runs (289 supported tasks) | episodes with an invalid turn | ends by run budget | material spec error rate |
|---|---|---|---|---|---|
| M1 | 293/300 = 97.7% | 1.135 | 0 | 7 | 72/280 = 26% |
| control (shuffled reward) | 294/300 = 98.0% | 1.111 | 1 | 5 | 69/280 = 25% |
| checkpoint-50 | 290/300 = 96.7% | 1.149 | 0 | 10 | 68/280 = 24% |

* **Paired against M1:** checkpoint-50 lost 4 tasks M1 passed and won 1 (net -3, -1.0 pp; 4 vs 1 discordant pairs is far from significant: exact McNemar p about 0.38). The control was 1 vs 2. The four losses all end by the run budget (4 runs) where M1 needed 1 to 3: `dv-5890de054d-polit`, `dv-a2d9bf9515-polit`, `dv-cb5887d1ae-polit`, `dv-ee373c6c75-sympt`.
* **Efficiency did not transfer to dev:** mean runs per supported task 1.149 against M1's 1.135 (paired difference +0.014, SE 0.021). The training-time gain (runs per rollout 1.52 against the control's 1.78, on the hard pool) is not visible on dev, where M1 already solves almost everything in 1.1 runs; there is little room to save, and the run-budget endings went up (7 to 10), not down.
* **Spec errors:** 24% against 26% (M1): no change within the intervals; the known width/height and end_s bugs are untouched, as expected (spec_acc weight 0, D-043).
* **What this does and does not say:** dev is saturated and is not the preregistered test of Q3a/Q3b (those are on the test splits, never run). It does say the training signal did not make the model more efficient on ordinary tasks, and that it may have made it slightly more willing to retry. A look at the four run-budget losses is the first thing to do if checkpoint-60 shows the same pattern.
