# Task splits rebuilt on the pinned FFmpeg (19 Nov 2026)

Why: three things changed at once, so every split hash changed: (1) FFmpeg 9.0.2 -> pinned 5.1.1-static (D-024, enforced), (2) 17 real/derived clips added to the corpus (D-033, 22 -> 39 clips), (3) the `context_first` held-out style replaced `technical` (D-027). No test split had ever been run (`reports/TEST_RUNS.jsonl` does not exist), so nothing evaluated is invalidated.

## Hashes (old -> new)
| split | tasks | old sha256 | new sha256 |
|---|---|---|---|
| train | 4486 -> 4473 | 4168061d2e | 66992faa31 |
| dev | 300 -> 300 | bdfc858837 | 635c5bd9bb |
| test-iid | 500 -> 500 | 5a9a8bf5bb | eec486876e |
| test-compositional | 200 -> 200 | 5162309301 | 533dc8702c |
| test-phrasing | 200 -> 200 | 21a3bbca0a | 62f2711640 |

Corpus manifest sha256 f3098b21e0 -> 97ce721e3c. Full hashes and the per-split family/difficulty counts: `MANIFEST.old.json` / `MANIFEST.new.json`; run log `build.log`; seed 20261115 unchanged.

## Guards (all hold)
- No `test-real` clip (`hevc_phone`, `screen_rec`, `wa_compressed`) and no restricted clip (`meridian_4k`) is an input of any task; `tests/taskgen/test_clip_roles.py` enforces both and passes on these files. `tos_avoff` (`av_skew`) is never drawn by F11, as designed.
- Leakage audit (`leakage.txt`, 4-gram Jaccard, gate 0.9 for the held-out splits): test-compositional max 0.750 (0 over), test-phrasing max 0.765 (0 over; was 0.692). test-iid 105/500 and dev 49/300 are over 0.9 by design (in-distribution wording; reported, not gated; was 65 and 28 before, because the new real clips are drawn into the same templates). test-phrasing mean Jaccard rose 0.243 -> 0.370: `context_first` wraps train core wording in a new framing (limitation already in the preregistration).

## What the new clips did to the mix (`clip-usage.json`)
- 2378 of 6304 clip uses (38%) are the new clips, and every one of them is ToS-derived: the scene content is narrower than the 39-clip count suggests (README limitation added).
- **Not used by any task:** `tos_webm` and `bbb_4k` (the existing webm family keys on `vp9`, not on the `webm` tag, so VP8 inputs are never drawn). The corpus holds them; the generators do not exercise them yet. Fix needs a family change and a re-build, so it is a Phase 1 decision, not done silently.
- Contents per split hit their targets (train 1500 contents -> 4473 tasks after dedupe of rendered wordings, was 4486). Failed references are dropped by design and counted in `MANIFEST.new.json` (`dropped`; e.g. 22 for F2+F9).
- Build time: ~16 min (03:36 -> 03:52 IST), 47 verification rounds with 3 workers (`build.log`). Results are cached per (content, reference, checker, FFmpeg).
