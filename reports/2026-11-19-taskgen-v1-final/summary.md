# Final Phase 1 task splits (19 Nov 2026)

This is the rebuild after commits f175332 (ingest), 9046422 (pin) and 8f68b9e (protocol 0.3.0). It is the ONE rebuild the owner asked for covering: (2) `-display_rotation` removed from the allowlist, (3) F3's webm intent widened to VP8 + VP9, plus the manifest probes refreshed with the pinned ffprobe (D-029). Seed 20261115, FFmpeg 5.1.1-static.

| split | tasks (prev -> now) | sha256 (prev -> now) |
|---|---|---|
| dev | 300 -> 300 | 635c5bd9bb -> 784c8017f9 |
| test-compositional | 200 -> 200 | 533dc8702c -> 19f599f1c5 |
| test-iid | 500 -> 500 | eec486876e -> bd01e887c0 |
| test-phrasing | 200 -> 200 | 62f2711640 -> 86188225de |
| train | 4473 -> 4472 | 66992faa31 -> 1651d8addf |

Corpus hash: now computed over the clips task generation can see (test-real and restricted clips excluded, owner rule): a later test-real clip changes no split. Proved by `tests/taskgen/test_clip_roles.py::test_adding_a_test_real_clip_changes_no_split_input` and by a cached re-run of this build: all five split hashes identical, only `corpus_manifest_sha256` (97ce721e3c -> 7055b86b33) changed.

## Guards
- No test-real or restricted clip in any task; no `-display_rotation` in any reference command; `tos_avoff` (av_skew) never drawn (`clip-usage.json`).
- `tos_webm` and `bbb_4k` are now drawn: 39 and 44 uses (before: 0), through the existing F3 webm intent.
- Leakage (`leakage.txt`): held-out splits stay under the 0.9 gate (see file); test-iid/dev overlap with train is by design (reported, not gated).
