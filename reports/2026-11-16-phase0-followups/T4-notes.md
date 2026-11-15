# T4 notes: B0 and fair base-model baselines (dev split only, n = 50)

Full table with taxonomy: `baselines-all.md`. Original B1/B2 rows are unchanged; the new rows are `B0-regex`
and `*-fair`. No test split was touched.

## B0 regex/preset baseline: 46/50 = 92% [81%, 97%]
- ~20 patterns (trim, range, last-N, gif, frames, mp3, mute, resolution, vertical/square/size, rotate, flip, fps,
  speed, volume/loudness, A/V offset, compress-to-size, merge, HEVC/compat), combined into one command per request.
- By steps: single-step 34/34, multi-step 9/10. By family: weakest F1 8/10, F12 4/5, F6 4/5, F3 7/8.
- Failures: the 3 ambiguous tasks (B0 cannot ask) and one multi-step ("cut off the first second, then speed up 2x").
- **X1 - B0 = +2.0 pts [-6, +12]: not distinguishable on this set.**
- **This number is optimistic and must not be read as "presets match a frontier model".** The patterns were written by
  the same person who wrote these 50 tasks, so they are partly fitted to the wording. It does show the dev set is too
  template-like to separate presets from models; EVALUATION Q7 needs phrasing-diverse splits (test-phrasing/test-real).
  B0 was not tuned after seeing results.

## Fair base-model baselines (small-model prompt with no example actions + JSON-schema constrained decoding)
| | original | fair |
|---|---|---|
| Qwen3-0.6B B1 / B2 | 0% / 0% | 0% / 0% |
| Qwen3-1.7B B1 / B2 | 8% / 8% | 8% / 8% |
- Constrained decoding removed unparseable output (0.6B: 44 -> 2 unparseable) but the models still fail: replies are
  valid JSON actions whose `args` break the harness grammar (`"-i h264_long"` as one string; whole command in one
  string; missing `{in:ID}`/`{out:ID}`). Taxonomy: 0.6B-fair 42 invalid_action; 1.7B-fair 42 invalid_action.
- 1.7B-fair asks a clarifying question on 3/3 ambiguous tasks (original: 0/3) but only refuses 1/3 unsupported.
- Reading: the gap to X1 is NOT only prompt formatting or JSON syntax. It is largely the strict argument-list/id
  protocol, which SFT on verified trajectories should teach; the validator was deliberately not loosened.
- The `spec` action is omitted from the fair prompt and schema (not needed to run or be graded; the 0.6B copied its example).

## Failure taxonomy
Defined in `eval/taxonomy.py` (9 categories, one per failed episode, from the transcript). X1's s13 (rotation)
transcript was lost in the Phase 0 OOM kill, shown as `unknown_transcript_lost`.
