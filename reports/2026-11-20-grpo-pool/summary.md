# GRPO pool: yield, breakdown and step count (21 Nov 2026)

**The pool is 358 prompts = 249 unique contents, below the 400-task target.** It is the file `pool-ids.txt` in this directory (sha256 `83b4401c75e28b53...`), consumed by `main_run --pool-ids ... --extra-train hard-v1`.

## What was sampled
Candidates (`candidates-manifest.json`): 1,813 train tasks = 1,513 from the standard train file that are copy-eligible, speed or frame-interval tasks, plus all 300 of the hash-pinned `hard-v1` file; seeded random order. K = 8 samples per task, M1 Q8_0, temperature 1.0, prompt v1, spec first, all reward terms recorded: 14,504 episodes (local, no money, no test split). `sample/records.jsonl` holds every sample.

## The pool and what defines it
A task is in the pool if its K = 8 group has nonzero variance in the reward **without `spec_acc`** (weight 0, D-043), so style-only variance does not count.

| | prompts | unique contents |
|---|---|---|
| sampled | 1,813 | 808 |
| **pool** | **358 (19.7% [18.0, 21.6])** | **249** |

(The train file renders each content in 3 styles, so prompts overcount distinct cases by about 1.4x here; the hard-v1 file has one style per content.)

## Which term creates the variance (358 groups; terms overlap)
* efficiency 329 groups, of which: runs differ among passed samples 187; **needless re-encode 48 (37 unique contents)**; pass differs 177
* pass varies 179; partial credit 143; invalid action 34; clarify 3
* the only varying term: efficiency/runs 145, partial 18, invalid 8 (pass is the primary term in 168)

By category (in pool / sampled): copy-eligible 166/696 = 24%, hard-v1 74/300 = 25%, speed 150/797 = 19%, standard train 284/1,513 = 19%, **frame-interval 10/133 = 8%** (low).

Mean K = 8 pass rate over the pool: 0.74 (the pool is mostly tasks that M1 usually, not always, solves).

## What this means for what GRPO is for (the preregistered Q3a)
The efficiency goal is partly supported and partly thin: **only 48 groups, 37 unique contents, show variance in needless re-encoding** (the Q3a target); most of the signal is in the number of runs and in pass/fail. GRPO can learn to avoid needless re-encoding from those 37 contents and to use fewer runs from about 190 others, but the re-encode lever is small. The pool being under 400 matters less than this: 166 copy-eligible prompts are in the pool, but only about a third of them differ in re-encoding between samples.

## Proposed step count: 60 steps (control: 30)
8 prompts per step. Epochs over the pool = 8 x steps / 358 prompts; epochs over unique contents = 8 x steps / 249.

| steps | prompts seen | epochs over prompts | epochs over unique contents |
|---|---|---|---|
| 30 (control) | 240 | 0.67 | 0.96 |
| **60 (proposed main)** | **480** | **1.3** | **1.9** |
| 100 (the old default) | 800 | 2.2 | 3.2 |

60 keeps the main run under two passes over the unique contents; 100 would show each content about three times (in different phrasings), which is where memorising a 249-case pool starts to show. Cost: Phase 0 measured 0.071 GPU-h per step for the toy setting, so 60 steps would be about 4 GPU-h against the 15 GPU-h cap; the real figure comes from the first control steps and the cap and stop rules stay.

## If you want a larger pool (not done)
The standard train file still has about 2,959 renderings that are neither copy-eligible nor speed nor frame-interval (and are not in `hard-v1`). They were not sampled. At a rate like the 19% of the "train" category they would add roughly 500 prompts but few new copy-eligible contents. A second batch would cost about 8 hours of local GPU and no money. You rejected a large scale-up earlier; this is only a pointer.

Files: `pool-ids.txt`, `pool/pool-summary.json`, `sample/` (records.jsonl, analysis.json), `candidates-manifest.json`, `candidate-categories.json`, `sampling.log`.
