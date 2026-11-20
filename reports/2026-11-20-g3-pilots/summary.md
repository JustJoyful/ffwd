# G3 pilots and criteria check (20 Nov 2026, overnight)

**Outcome: G3 auto-go did NOT trigger. Criteria (a) and (d) fail; (b) and (c) hold. By your rule I stopped after the pilots.** Nothing else was done: no full train set, no shuffled-reward control, no GRPO, no checkpoint selection, no test split touched, no money spent (DeepSeek ledger still $2.675 of $4).

## Criteria

| | Criterion | Result |
|---|---|---|
| (a) | in-band (20-80%) share >= 25% on widened + recovery pilots AND >= 400 in-band train tasks estimated at full scale | **FAIL.** 53/600 = **8.8% [6.8%, 11.4%]**. Estimated in-band tasks: 265 at 3,000 candidates [205, 341], 353 at 4,000. Both thresholds missed even at the upper end of the sizing. (`g3-criterion-a.json`, computed by `eval/g3_criteria.py`) |
| (b) | every perturbed recovery command fails the checker, every reference passes (tests green) | **holds.** `tests/taskgen/test_hard_and_recovery.py` green. Also in the generation manifests: `all_references_passed: true` for the 300-task pilot and the 250 dev recovery tasks (every emitted task re-verified: base reference passes, perturbed run executed and failed at least one checker field). |
| (c) | no test-split file read anywhere (split guard tests green) | **holds.** 151 tests passed (`tests/taskgen`, `tests/grpo`, `tests/eval/test_g3_criteria.py`, `test_recovery_eval.py`), including the guard tests and the pool-build test that blocks test-split path reads. Pilot candidates are train-bucket only; recovery bases are train tasks; the dev recovery set is built from dev. |
| (d) | Kaggle kernel uses the pinned FFmpeg (sha256 check passes in the log) and pushes checkpoints to the Hub every 10 steps | **FAIL (no evidence, not "unclear").** Code exists (`ffmpeg_pin.install()` raises on a sha256 mismatch; `main_run.py --hub-repo` with save every 10 steps), but there is no main-run kernel and no Kaggle log showing either working. Both API-pushed kernel logs show `get_secret('HF_TOKEN')` -> HTTP 400, so an API-pushed kernel cannot push to the Hub; the existing resume notebook needs `GITHUB_TOKEN` + `HF_TOKEN` secrets and clones `main` from GitHub, which is 66 commits behind. |

## Pilot measurements (train tasks only; M1 Q8_0, K=8, temperature 1.0, band 2-6 passes of 8)

| pilot | tasks | in band | too easy (>80%) | too hard (<20%) | share [95% CI] | mean pass rate |
|---|---|---|---|---|---|---|
| widened (hard-variant pool: more 3-4 family tasks, more F2/F6/F7/F8/F10/F11, more F9 combos) | 300 | 23 | 256 | 21 | 8% [5%, 11%] | 0.89 |
| recovery-start (gold spec + a perturbed run the checker fails) | 300 | 30 | 228 | 42 | 10% [7%, 14%] | 0.81 |
| pooled | 600 | 53 | 484 | 63 | 8.8% [6.8%, 11.4%] | |

For comparison, the original train sample was 3% in band (T18). Widening moved it to 8% and recovery starts to 10%: better, but about a third of what you asked for.

Pass-count histograms (passes out of 8): widened 8/8 x244, 7 x12, 6 x6, 5 x5, 4 x3, 3 x4, 2 x5, 1 x5, 0 x16. Recovery 8/8 x220, 7 x8, 6 x11, 5 x1, 4 x10, 3 x3, 2 x5, 1 x8, 0 x34. The distribution is two spikes (always right, always wrong): at temperature 1.0 M1 is nearly deterministic, so most prompts give a GRPO group with no reward variance (0/8 or 8/8: 514 of 600 = 86%).

By group (`widened-report/summary.md`, `recovery-report/summary.md`): in the widened pilot the in-band share rises with family count (1-2 families 0%, 3 families 5%, 4 families 16% [10, 24]); F3 and F5 tasks are somewhat higher (14-15%); F10 tasks are 0/51 in band. In the recovery pilot the share is flat (9-13% by family count) and F6 is highest (19%). Intervals are wide for the small groups.

## M1 recovery rate on dev (dev only; `dev-recovery/recovery.json`)

* **Perturbed start** (each dev task re-run from the gold spec + a verifiably failing run; 250 of 300 dev tasks got a verified perturbation): M1 recovered **225/250 = 90% [86%, 93%]**, mean 2.22 runs. Weak operators: `speed_wrong` 1/7 and `frames_interval` 1/6 (small n); everything else 83-100% (`swap_acodec` 26/26, `fps_wrong` 13/13, `halve_t` 55/56, `crop_wrong` 24/29, `drop_af` 19/22).
* **Natural recovery** (the existing dev run: tasks whose first run failed): 15/22 = **68% [47%, 84%]** ended passing.
* This contradicts my earlier reading ("M1 mostly repeats a failing command"): given an explicit failing run, M1 usually fixes it, except for speed and frame-interval errors. Caveat: the perturbed starts are only the kinds of error my operators can produce.
* Method caveat: this run used the 4-slot server (`-c 32768 -np 4`) rather than the config's `-np 1`; the harness issued one request at a time, greedy.

## Why (a) fails and what it means

The pilots show the opposite of what I expected: the model is not failing the harder train tasks, it is nearly deterministic on them. 73-81% of the tasks are 8/8 and the in-band tasks are a thin slice between two spikes. At full scale, GRPO with 8 prompts x 8 samples per step would see on average about 0.7 in-band prompts per step (about 1.1 prompts with any reward variance). That is a weak training signal, and the preregistered stop rule "no-signal share > 60% for 10 steps" would trip at once (expected no-signal share about 86%) unless the sampler is restricted to the filtered in-band set. The design allows that filter, but then the 400-task floor is exactly what the criterion protects.

## Proposal (your decision; I have not started any of it)

1. **Stop at M1 for training and prepare G4 instead** (own clips, ~100 test-real requests, preregistration FINAL). M1 is 98% on dev and "SFT nearly sufficient" is the preregistered reading. GRPO would be justified only by headroom on held-out sets, which I cannot measure without touching test. This is the cheapest option; it costs the GRPO result (M3) in the table.
2. **Scale the pilots to reach 400 in-band tasks.** At the observed 8.8% that is about 4,500 candidates (400/0.0883; CI-based range about 3,500-5,900). Cost: no money, but about 18 h of local GPU (the pilots took 71 min for 300 widened tasks and 63 min for 300 recovery tasks at K=8 on the RTX 3050) plus generation time. It still leaves (d) and the rollout work below.
3. **Fix (d) by running the main run through the Kaggle web UI** (not the API): you attach `HF_TOKEN` and `GITHUB_TOKEN` as notebook secrets, push `main` to GitHub first (66 commits behind; the notebook clones from there), run a main-run notebook with the pin install and Hub push, and I read the log for the sha256 line. Needed under any GRPO option.
4. **Not built, needed to use the recovery pool in GRPO:** rollout support for scripted openings (`rollout.py` TokenPolicy masking the opening turns). The pilots use `OpeningPolicy` at sampling time only.
5. If we go GRPO: options 2 + 3 + 4, and say up front that the likely outcome on in-distribution dev is "no change" (M1 98%). The interesting measurement would be test-compositional, which is G4.

I would pick option 1 now, and keep options 2-4 as the plan if you want GRPO regardless.

## Reproduce

```
uv run python -m training.taskgen.hard --out data/tasks-hard/widened-pilot --n 300
uv run python -m training.taskgen.recovery --tasks <train base tasks> --out data/tasks-hard/recovery-pilot --n 300
uv run python -m training.taskgen.recovery --tasks data/tasks/dev/v1.jsonl --out data/tasks-hard/dev-recovery --workers 2
uv run python -m training.grpo.taskfilter --tasks data/tasks-hard/widened-pilot/tasks.jsonl --policy-config eval/configs/m1-0.6b-q8.toml --k 8 --workers 4 --phase1 --out <dir>
# recovery pilot: same with --tasks data/tasks-hard/recovery-pilot/tasks.jsonl --openings data/tasks-hard/recovery-pilot/recovery.jsonl
uv run python -m eval.g3_criteria --tables <widened pass_rates.json> <recovery pass_rates.json> --out <file>
uv run python -m eval.recovery_eval --run reports/2026-11-20-m1-dev/M1-0.6b-q8 --recovery data/tasks-hard/dev-recovery --model-config eval/configs/m1-0.6b-q8.toml --out <dir>
```

Files here: `pilot-data/` (the pilot task files, recovery openings and generation manifests), `*-taskfilter/` (per-task pass counts), `*-report/` (group tables), `dev-recovery/` (episodes, results, recovery.json), `g3-criterion-a.json`, logs (`server.log.gz` is the llama-server log). llama-server is stopped and the GPU is free.
