# Phase 1 milestone: M1 trained and evaluated; stopped before GRPO (20 Nov 2026, 03:30 IST)

Everything since the bulk teacher run, in one place. Dev only; **no system has been run on any test split.** DeepSeek spend: $2.675 of $4 (ledger unchanged since the bulk run and paraphrases); everything below cost $0.

## 1. What M1 is and how it was made
* Data (`reports/2026-11-19-teacher-bulk/`, `reports/2026-11-19-sft-data/`): teacher bulk 3490 episodes, 3199 kept after the label filter ($2.30, cache-hit 84%); paraphrases; oracle trajectories (D-032). SFT set 6032 train / 333 val examples: 50% teacher, 31% teacher paraphrases, 18% oracle.
* SFT on a Kaggle T4: Qwen3-0.6B, all-linear LoRA r16/alpha32, lr 1e-4, **2 epochs, batch 2 x accum 8 (effective 16)**, 754 steps, about 5 h (19:00-00:02 IST). The config default is 3 epochs, 4 x 4; the deviation is recorded in D-037 (T4 memory for the batch; the reason for 3 -> 2 epochs was not recorded). Final losses (from the Kaggle log the owner pasted): train loss 0.0997 (run mean), **eval loss 0.0777**, flat at the end; reason for 2 epochs: to save time (owner). Details in the addendum of `reports/2026-11-20-m1-dev/summary.md`. (The script had deleted its checkpoints; fixed in `049bbdf`.)
* Export: merged fp16 model, then llama.cpp b12032 `convert_hf_to_gguf.py` and `llama-quantize` to Q8_0 (640 MB), served by `llama-server` with the agent chat template (D-026, D-036). Hashes in `reports/2026-11-20-m1-dev/manifest.json`.

## 2. Results (dev v1, 300 tasks; Wilson 95% CIs; failed/invalid episodes count as failures)
| | overall | 1 fam | 2 fam | 3 fam | 4 fam | ambiguous | unsupported |
|---|---|---|---|---|---|---|---|
| B0 (regex) | 178/300 = 59% [54, 65] | 83% | 62% | 44% | 27% | 0/2 | 9/9 |
| **M1 (GGUF Q8_0)** | **293/300 = 98% [95, 99]** | 71/72 | 125/127 | 68/71 | 29/30 | 2/2 | 9/9 |

0 invalid turns in 300 episodes; 267 tasks needed one run; 18.5 min for the whole split on the RTX 3050. `reports/2026-11-20-m1-dev/`.

**Per the preregistration: M1 is >= 90% on dev, so this report says "SFT nearly sufficient": little headroom is left for GRPO and any GRPO gain is bounded by it. GRPO still runs as preregistered if the owner approves (G3).**

This is an in-distribution dev number (same generator, templates and clip pool as train, different content keys); test-compositional, test-phrasing and the owner's own test-real clips are the real questions and are not run.

## 3. Checks on the number
* **Leakage (dev vs SFT sources):** 0 shared task ids or content keys; 44/300 dev requests are word-for-word training requests and 11/300 share clip and gold spec with a training task; M1 scores 246/252 = 98% on the rest, so the overlap does not drive the result.
* **HF fp16 vs GGUF Q8_0 parity** (`reports/2026-11-20-m1-parity/`): 100 seeded dev tasks, 98/100 vs 99/100, 99% agreement, McNemar p = 1.0, paired difference +1 pp [0, +3]; transcripts byte-identical on 65% (first turn 86%): the differences are free-text `note` wording (14), unscored spec details (14), first run command (6). With both at 98-99%, 100 tasks only rule out a large Q8_0 loss.
* **The 7 failures** (`reports/2026-11-20-m1-dev-failures/`): all hit the 4-run limit; 7/7 model errors, 0 checker false negatives; one generator wording ambiguity (speed-before-trim: the gold applies the trim to the source timeline, M1 follows that on 60/61 speed+trim tasks). 5 of 7 involve F9, concentrated in join + remove sound (F2+F9 0/3, F9 overall 80/85): the concat filter keeps an audio branch. The model repeats a failing command almost unchanged instead of using the checker feedback.

## 4. Train-side headroom for GRPO (T18, `reports/2026-11-20-t18-pass-rates/`)
K=8 at temperature 1.0 on train tasks: **in-band (20-80%) share 3% [2%, 6%]** (302-task seeded sample) and 6% [3%, 13%] on the 110 train tasks never used in SFT; roughly 140 in-band tasks in the whole train set. Below the 30% line, so a **difficulty-widened train set is proposed, not built**: oversample the non-easy patterns (3-clip joins and join + strip audio, tight size caps, dB gain/loudness after short trims, audio delay, frame grab to JPG, GIFs, crop-to-square needing upscale, 3-4 family train combos), train styles and combos only, no split changes. About 10x enrichment of the hard variants is needed to reach 30%; about 3,000-4,000 candidates for about 1,000 in-band tasks; a 300-candidate pilot first. Yield is unproven.

## 5. Evaluation-protocol changes (dev-time, before any test run)
* **D-038 / preregistration:** `unsupported` tasks are graded on the action alone (refused, nothing run); `nearest_supported` is descriptive and not scored in eval or reward (`config.REWARD_SCORES_NEAREST_SUPPORTED = False`, pinned by a test). No dev number changes (`score()` never read it). The teacher-data label filter stays as SFT data hygiene.
* **D-039 / preregistration:** exact-duplicate requests vs train: test-iid **104/500 (20.8%)**, test-compositional 0/200, test-phrasing 0/200, dev 45/300; 27 of the 104 also share clip and gold spec. test-iid is reported on the full split AND the 396-task deduplicated subset (ids pinned by sha256; `final_report(iid_dedup_ids=...)` is built and tested). Q2-Q4 and Holm stay on the full split; the dedup column is descriptive. **Open: owner to confirm Holm on the full split.**
* 24/200 test-phrasing tasks share clip and gold spec with a train task by design (held-out wording of known tasks).

## 6. Process and tooling added
`eval/hf_policy.py`, `eval/hf_parity.py` (HF-vs-GGUF parity); `eval/leakage.py --exact-out`; `eval/passrate_report.py`; `taskfilter` with parallel workers, resume, seeded sampling and job-dir cleanup; the Kaggle SFT script keeps checkpoints, `trainer_state.json` and the log and no longer ships its venv. Full suite 714 passed / 3 skipped, ruff and black clean (run after the last code change). Commits: `fb1576b` M1 dev, `6b5a222` leakage + dedup, `5cc3af1` prereg + D-037..D-039, `049bbdf` Kaggle script, `1c88f83` taskfilter, `dc1a147` parity, `b5f2d0d` failures, `3b63b8e` T18.

## 7. Open items for the owner
1. **G3:** approve GRPO (<= 15 GPU-h) and the 30-step shuffled-reward control, or first the widened train set (about a day of work plus the pilot), or stop at M1 given 98% dev.
2. **G4:** preregistration FINAL, the single test run, your ~10 own clips and ~100 test-real requests.
3. Holm on the full vs deduplicated test-iid (default kept: full).
4. ~~Paste the Kaggle log tail~~ done 20 Nov (see section 1).
5. Decide `remove_object` -> F4 label strictness (affects data hygiene only after D-038); whether to run a 1.7B SFT (not started, per the owner).
6. Hub pushes (corpus, model) and the HF model card are not done.

## 8. Not done, by design
No test-split run of any system; no GRPO; no 1.7B SFT; no widened train set; the full 4472-task pass-rate table (about 11 h; resumable); no re-run of the Kaggle script after its fix (tested for structure only).
