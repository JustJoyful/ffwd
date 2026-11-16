# spike-v1 changes relative to spike-v0

50 v0 tasks -> 49 carried over (new tasks are added separately, ids n01..).
Invariants (output duration and audio presence must match the input unless the spec changes them),
the rotation convention and the frame-count rule are CHECKER changes (checker v1.2) that apply to
all tasks; they need no per-task edits except where listed.

- `s13-rotate-cw-lossless`: video.rotation 270 -> 90: one clockwise convention (spec.schema.json)
- `s15-turn-left`: added video.rotation 270 (90 counterclockwise): direction is now checked
- `s19-frame-every-2s`: frames: interval 2 + expected_count 5 (10 s clip, samples at 0,2,4,6,8)
- `s20-every-second-jpg`: frames: interval 1 + expected_count 10 (10 s clip, samples at 0..9)
- `m03-frames-2-to-7`: frames: interval 1 + expected_count 5 (window 2 s..7 s, samples at 2..6)
- `m05-merge-mute`: DROPPED, duplicate of s06 (merge + remove sound)
- `m09-rotate-cw-30fps`: added video.rotation 90 (clockwise): direction is now checked
- `u01-remove-person`: families ['F4'] -> [] ; nearest_supported null (nothing close)
- `u02-add-subtitles`: families ['F3'] -> [] ; nearest_supported null (nothing close)
- `u03-cinematic-grade`: families ['F3'] -> [] ; nearest_supported null (nothing close)
