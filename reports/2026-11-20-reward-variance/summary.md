# Reward variance of K=8 groups, full reward (20 Nov 2026)

Owner question: how many groups have nonzero TOTAL-reward variance (all terms, not just pass), and which term creates it?

**Method note:** the pilots kept only pass/fail per sample, so their transcripts do not exist. I re-sampled 100 seeded tasks from each of the widened pilot, the recovery pilot (scripted opening) and the T18 train sample (302 train tasks), K=8, temperature 1.0, prompt v1, spec first, same M1 Q8_0 and harness, and kept every sample's reward terms (`eval/reward_variance.py`, `training.grpo.telemetry.grpo_reward`, weights from `config.REWARD_WEIGHTS`). 2,400 episodes, train tasks only, no money. Different samples from the pilots (same distribution). Wilson 95% intervals; n = 100 groups per set.

## Share of groups with signal

| set (100 groups) | total-reward variance | pass variance only (the old view) | signal with NO pass variance |
|---|---|---|---|
| widened | 47 [38, 57]% | 8 [4, 15]% | 39 [30, 49]% |
| recovery-start | 17 [11, 26]% | 12 [7, 20]% | 5 [2, 11]% |
| T18 train sample | 32 [24, 42]% | 11 [6, 19]% | 21 [14, 30]% |
| **pooled (300)** | **32 [27, 37]%** (96 groups) | 10 [7, 14]% (31) | **22 [17, 27]%** (65) |

## Which term creates it (pooled, 300 groups)

Groups where the term varies at all: spec_acc 57 (19%), efficiency 51 (17%), pass 31 (10%), partial 23 (8%), invalid 2, clarify 1.
Term with the largest weighted spread ("primary") among the 96 groups with signal: spec_acc 40, pass 31, efficiency 19, partial 4, invalid 2.
Groups where it is the ONLY varying term: spec_acc 40, efficiency 15, partial 4.
Efficiency splits into: **runs** differ among passed samples in 30 groups; **needless re-encode** in 1 group; pass differs (efficiency inherits it) in 31. Of the 65 groups with signal but no pass variance: spec_acc 45, efficiency/runs 20, partial 4, invalid 2, clarify 1.

By set: widened is dominated by spec_acc (36 groups vary, 28 only in it); recovery signal is mostly pass (12) and efficiency/runs (16); T18 is spec_acc 20, efficiency 17, pass 11.

## Re-encode and runs

* Samples (all three sets, passed samples only): needless re-encode 5 of 2,153 (0.2%); in the widened and recovery sets 0 of 1,402. That is rarer than on dev below because these denominators are all passed samples, not tasks whose reference is stream-copy.
* Mean runs per sample: widened 1.37, recovery 2.52 (the scripted opening counts as one run), T18 1.20.
* **Dev, existing greedy M1 run, scored with the real reward** (`eval.reward_variance dev`): mean runs 1.13 per supported task (267 of 289 needed exactly 1, 12 two, 3 three, 7 four); needless re-encode on **8 of 31 tasks whose reference is stream-copy-only = 26% [14%, 43%]**, and all 31 of those passed (the checker does not penalise it; only the efficiency term does); mean efficiency term 0.92; mean total reward 1.17.

## What this means (my reading)

* Counting the whole reward, 32% of groups have a nonzero advantage, not 10%. Roughly 8 prompts x 32% = 2.6 informative groups per step instead of 0.8.
* But two thirds of that extra signal (spec_acc, 45 of 65) comes from the **weakest and most gameable term**: the field-level F1 between the emitted spec and the gold spec, weight 0.2. GRPO normalises advantages within a group, so a tiny spec_acc difference in an all-passing group becomes a full-size advantage. The model would be optimising "write the spec the way the generator does" more than "get the command right". The efficiency/runs part (20 groups) is a legitimate signal (fewer runs).
* Needless re-encode almost never occurs at temperature 1.0 in these sets, so it is not a significant source here.
* Not measured: whether spec_acc differences are real spec errors or equivalent alternative specs (that needs reading transcripts; I did not).
* Caveat: n = 100 groups per set; pooled n = 300; the three sets are different distributions, so the pooled share is a mixture, not an estimate for any one training set.

Files: `widened/`, `recovery/`, `t18/` (`records.jsonl` per sample, `analysis.json`), `analysis-all.json`, `t18-sample-tasks.jsonl` (the 302 T18 train tasks), `server.log`, `sampling.log`.
