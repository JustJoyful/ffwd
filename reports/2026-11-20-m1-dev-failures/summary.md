# The 7 M1 dev failures, read one by one (20 Nov 2026)

Source: `reports/2026-11-20-m1-dev/M1-0.6b-q8` (293/300). All 7 ended `run_budget` (4 runs used, no passing check). Correction to the premise "all F9 multi-family": **5 of 7 involve F9**; one is F6 alone, one is F4+F10+F1. Question asked for each: model error, checker false negative, or generator issue?

**Verdict: 7/7 model errors, 0 checker false negatives, 1 task with a real generator wording ambiguity on top of a model error.** Every failed checker field is true of the output the model produced (720 vs 1080 px, size above the cap, audio present, -29.7 LUFS vs -14, an ffmpeg error).

| Task | Families | What the model did | Cause |
|---|---|---|---|
| dv-658939d89a | F2+F9 (join, remove sound) | Joined with `concat=n=2:v=1:a=1` and `-map [v] -an`, leaving the audio output of the filter unconnected: ffmpeg "Filter concat has an unconnected output". Repeated the identical command 3 more times. | Model: does not know that "no audio" must be `a=0` with video inputs only. |
| dv-958fbe818c | F2+F9 | Run 1 passed ffmpeg but `-map [a]` kept an audio stream (`-an` does not remove an explicitly mapped filter output): `audio.present` true. Then broke the filter (`[a0]`/`[a1]` labels that do not exist) and repeated it. | Model. (HF fp16 solved this one: the single parity discordance.) |
| dv-f383406e52 | F2+F4+F9 | Same pattern as above (kept `-map [a]`, then dropped the `[0:a]aresample` labels, "Stream specifier 'a0' matches no streams"). | Model. |
| dv-5fb9d249d9 | F6+F1+F9 | Size cap 1 MB: `-crf 30` plus `-b:v 1000k`/`800k`: libx264 uses CRF and ignores the bitrate, so the size stayed 1,335,733 bytes on three attempts, then it invented a flag (`-b:a:a0`) that the validator rejected. | Model: ineffective rate control, no use of feedback. |
| dv-b7e8c4b492 | F6 | Size cap 2 MB: bitrate 1600k video + 96k audio, never recomputed from the duration; four near-identical runs at 2.13-2.17 MB. | Model: no bitrate-from-size arithmetic. |
| dv-f1923afb25 | F4+F10+F1 | `-t 2` before `-i`, so single-pass `loudnorm=I=-14` sees only 2 s and ends at -29.7 LUFS. The reference puts `-t 2` after the input and passes. Then tried `loudnorm=I=-14:linear`, which is invalid without measured values (ffmpeg error) and repeated it. | Model. Checker is right: the output really is -29.7 LUFS. Note for the generator: single-pass loudnorm on short clips is fragile and the reference passes only because of option order. |
| dv-12ea3f96c9 | F12+F9+F1+F4 | Spec said 1080x1080 but the run used `crop=720:720` (no scale-up of the 720p source) on all 4 runs, ignoring "expected 1080, actual 720". | Model, **and a generator ambiguity**: see below. |

## Generator issue on dv-12ea3f96c9 (request wording vs gold)

The request reads "slow this video down to 0.5x speed and then strip the audio out and then keep only 0:00 to 0:02 and then crop...". Read literally the trim applies after the slowdown (2 s output), but the gold and the reference apply the trim to the **source** timeline and then slow it (4 s output; `time.end_s = 4.0`). The model's own run produced 2.0 s and the checker reported `time.duration_s expected 4.0 actual 2.0`: so even with the size fixed this run would have failed on the literal reading. This is a convention the generator uses for every F12+F1 combination regardless of the order the steps are mentioned. M1 learned the convention: it passes **20 of the 21** dev F12+F1 tasks whose request mentions the speed step before the trim step (regex heuristic), and 60 of 61 F12+F1 tasks overall, so this task is a slip. The ambiguity is still real for human requests (test-real): a person who says "slow it down, then keep the first 2 seconds" means 2 seconds. Recommendation (not done, no rebuild): either word the speed-before-trim requests unambiguously ("... the first 2 seconds of the original ...") in a future generator version, or score test-real tasks with that reading in mind.

## Patterns

* **F9 is not a general weakness:** F9 tasks pass 80/85 overall; the failures are concentrated in **F2+F9 (join + remove sound): 0/3**, one capability gap (concat with `a=0`) that more targeted training data could close.
* **The model does not use checker feedback to change its command:** in 5 of the 7 episodes the last two runs are the same command or differ by a flag that has no effect. This is the headroom GRPO is meant to use (reward for fixing a failed run); it is also the clearest argument that dev 98% leaves little room to show it.
* Size-cap tasks (F6) fail 2/22 on dev; loudness (F10) 1/26.

Method: read `episodes.jsonl` of the 7 failing tasks (gold spec, emitted spec, every run and its checker observation, ffmpeg stderr tails), and the reference solutions in `data/tasks/dev/v1.jsonl`. Dev only, no spend.
