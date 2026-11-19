# T18: M1 pass-rate table on TRAIN tasks (20 Nov 2026)

Train tasks only (never dev/test). M1 = GGUF Q8_0 through llama-server (b12032, 4 slots), prompt v1, spec first, **K = 8 samples per task at temperature 1.0** (GRPO's rollout temperature), band 20-80% (2-6 passes of 8). Wilson 95% intervals. No spend.

## Result: the in-band share is 3-6%, far below the 30% line

| sample | tasks | in band | too easy (>80%) | too hard (<20%) | share in band |
|---|---|---|---|---|---|
| seeded random sample of the train set (stopped by hand at 302 of 1000) | 302 | 9 | 285 | 8 | **3% [2%, 6%]** |
| of those, tasks M1 was fine-tuned on | 294 | 9 | 279 | 6 | 3% [2%, 6%] |
| **all 110 train tasks that appear in no SFT source** (never trained on) | 110 | 7 | 96 | 7 | **6% [3%, 13%]** |

Estimate for the whole train set (4472 tasks): about 3% in band, roughly **140 tasks** (plausible range ~90-270). The "never trained on" row answers the obvious objection: memorisation is not why the table is so easy; M1 is simply strong on this task distribution (dev 98% at greedy). Per-group tables with intervals: `summary-groups.md` (302-task sample) and `unseen/summary-groups.md` (110 unseen). Highest in-band shares are small-n and noisy: 4-family tasks 18% [5%, 48%] (unseen) and 0% [0%, 24%] (seen sample); F8 (GIF) 14% [3%, 51%]; F6 (size) 8%; difficulty 3 8%. No group comes anywhere near 30%.

## Which tasks are not too easy (17 of the 302)

Pass rates by exact task, grouped by what goes wrong (the same patterns as the 7 dev failures):
* **Frame grab (F7):** "grab just the first frame as a JPG" 0/8; "save the first frame as an image (jpg)" 1/8.
* **Audio gain/delay/loudness (F10, F11):** "make this video 6 dB louder" 0/8 while "boost the volume by 6 dB" is 6/8 (wording-sensitive); "push the audio back by 0.3 seconds" 1/8; scale + trim + normalise to -23 LUFS 0/8.
* **Joining (F2):** three clips back to back + resize 0/8; join + strip audio 0/8 (the dev failure pattern).
* **Size cap (F6):** "smaller than 2 MB" 2/8. **GIF (F8):** 240 px wide 0:06-0:09 2/8.
* **Compositions with a crop to 1080 square / vertical 1080x1920 and fps or speed changes (F12+F4, F9+F4+...):** 4-6 of 8; 4-family trim + slow + flip + remove sound 1/8.
About half of the non-easy tasks are in band (9 of 17), half too hard (0-1 of 8), so most of the headroom sits just outside the band.

## Proposal (NOT built): a difficulty-widened train set

Why not just widen the band: the plan says to widen the generator's mix, not the band (T18 step 4), and a 0-1/8 task gives GRPO almost no signal anyway.

**Idea.** Add a "hard-variant" train mix that oversamples exactly the patterns above, using train styles and train family combinations only (never held-out styles or combos; deduplicated against every split's content keys and requests, with the 4-gram guard):
1. F2: 3-clip joins, joins with audio removal (`concat ... a=0`), joins with a resize.
2. F6: size caps tight relative to duration (needs a bitrate = size / duration calculation), with and without audio.
3. F10/F11: gain in dB phrased several ways, loudness normalisation after a short trim, audio delay.
4. F7/F8: frame grab as JPG/PNG, GIFs of short windows with a given width.
5. Crop/vertical/square targets that need upscaling a 720p source, combined with fps or speed changes; 3-4 family train compositions.

**Estimate (crude, from the data above).** Natural density of non-easy tasks is about 5.6% (17/302) and half of those are in band, hence the 3%. Reaching 30% in band therefore needs roughly 60% of the new tasks to be non-easy, about **10x enrichment** over the natural mix. The patterns above are enumerable and parametric, so a 10x enrichment is plausible but **unproven**: until the new tasks are sampled, 30% is a target, not a forecast. Sizing: for about **1,000 in-band tasks** (enough for a ~100-step GRPO run at 8 prompts per step without heavy repetition) at an assumed 25-35% yield, generate about **3,000-4,000 candidates**, screen with K=4 (about 14,000 episodes at about 0.9 episodes/s = about 4-5 h of local GPU) and re-sample survivors at K=8 (about 1 h more). No DeepSeek spend: GRPO needs only the gold spec and the checker, not a teacher.

**Risks / what I would check first.** (a) Adding tasks must not move the existing hash-pinned splits: a separate module and seed writing a new file `train-hard`, with a test that `MANIFEST.json` split hashes are unchanged. (b) The yield could be well under 25% if M1 simply solves the new variants too; a 300-candidate pilot (about 20 min) would give the real yield before committing. (c) Some hard variants may expose checker or wording problems rather than model weakness (as the speed-before-trim wording on dev did): each new pattern needs its reference solution verified (`eval.verify_tasks`) first.

Context for the G3 decision: dev is 98% and the preregistration says this must be reported as "SFT nearly sufficient"; a GRPO gain is bounded by that headroom, and the in-band share above is the same fact seen from the training side.

## Caveats
* The 302-task table is a partial run (stopped by hand at 302 of a seeded 1000-task sample); it covers exactly the finished tasks, in sample order. In-flight tasks at the stop (at most 4) are excluded, which can bias against the slowest episodes by at most that amount. The unseen-task table is complete (all 110).
* The unseen 110 are tasks no teacher-kept, paraphrase or oracle trajectory covers: partly tasks DeepSeek failed, partly unreached ones; 46 of them are ambiguous/unsupported. They are not a random sample of the train set; they are the best available "unseen" set.
* Pass rates are for the Q8_0 GGUF server at temperature 1.0, K = 8: a rate of 1/8 and 2/8 are noisy (a task with true rate 0.25 reads as 0-1/8 about 37% of the time).
* Not done: the full 4472-task table (about 11 h), the widened set, any GRPO. `taskfilter` resumes from `rows.jsonl`, so extending the sample later costs only the new tasks.

Compute: about 1 h (302-task sample) + 20 min (unseen) of GPU, now freed (GPU 0%, 37 MiB, no llama-server). Files: `taskfilter/{pass_rates.json,rows.jsonl}`, `unseen/taskfilter/...`, `summary-groups.md`, `server*.log`, `run.log`.
