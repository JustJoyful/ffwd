# Paraphrase robustness (dev only)

44 of 50 tasks kept; same tasks on both sides. Wilson 95% CIs; difference = paraphrase − original, paired bootstrap 95% CI.

| System | Original | Paraphrase | Diff (pp) |
|---|---|---|---|
| B0 regex/preset | 41/44 = 93% [82%, 98%] | 31/44 = 70% [56%, 82%] | -22.7 [-36.4, -11.4] |
| X1 DeepSeek V4 Flash | 42/44 = 95% [85%, 99%] | 42/44 = 95% [85%, 99%] | +0.0 [+0.0, +0.0] |

## Tasks whose outcome changed

**B0 regex/preset**: `s07-iphone-powerpoint` True→False, `s10-vertical-9-16` True→False, `s14-upside-down` True→False, `s21-first-frame` True→False, `s26-remove-sound` True→False, `s29-boost-20db` True→False, `s33-delay-audio-200ms` True→False, `m02-iphone-first-2s` True→False, `m05-merge-mute` True→False, `m07-webm-to-720p-mp4` True→False

**X1 DeepSeek V4 Flash**: none

## Dropped paraphrases

- `s03-last-2s`: judge: NO — “Just the final 2 seconds of this clip is all I need.”
- `s31-audio-half-second-behind`: digits differ — “the sound's lagging behind the picture by 0.5 seconds, can you fix that”
- `s34-speed-2x`: digits differ — “Can you make this video play twice as fast?”
- `s36-half-speed`: digits differ — “slow it down to 50%”
- `m06-cut-then-2x`: digits differ — “trim the opening 1 second, then double the speed of what's left”
- `u03-cinematic-grade`: judge: NO — “give it a cinematic look, throw on a teal and orange colour grade”

## Reading it
- B0 fell 93% → 70% (−22.7 pp, CI excludes 0). All 10 new failures are the same kind: no pattern matched, so B0 answered `unsupported`. Its high Phase 0 score reflected author-fitted wording, as flagged.
- X1 was unchanged at 42/44 on both sides (same two failures: `s13-rotate-cw-lossless`, `a02-make-smaller`). The paired bootstrap CI is [0, 0] only because every difference is 0; the Wilson intervals are the informative ones.
- The X1 − B0 gap on unseen wording is +25 pp; on the originals it was +2. This supports the model over presets, which the original task set could not show.
- Caveats: n = 44; paraphrases are one DeepSeek sample each and the paraphraser is the same model family as X1 (could favour X1); the digit rule dropped legitimate rewordings ("half" → 0.5, "2x" → "twice") and the judge dropped two that look fine to a human reader, so speed-change tasks are underrepresented. Dropped items were not retried, by preregistration.
- Cost: paraphrase + judge $0.0050 (cap $0.02); X1 on paraphrases $0.0229 (cap $0.04). B0 sha256 unchanged since FREEZE.md.
