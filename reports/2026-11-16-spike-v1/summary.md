# spike-v1: checker v1.2 and task revisions (16 Nov 2026)

spike-v0 and the Phase 0 report are unchanged (sha256 pinned in a test). Decisions: D-024 (proposed), D-025.
Nothing paid was run. B0, base 1.7B and X1 on spike-v1 wait for the owner's new tasks and clips.

## What was asked and what happened
| # | Item | Result |
|---|---|---|
| 1 | Implicit invariants | Done. Duration and audio presence must match the input unless the spec changes them (`time.start_s/end_s`, `audio.present`; offset specs allow +-offset). Merge = sum of inputs. Video/audio streams required for those kinds. Conformance case "0.1 s H.264 output must FAIL s07" is in `checker-invariants.jsonl` and fails with `implicit.duration_s`. 11 invariant cases in total. |
| 2 | `-display_rotation` in ffmpeg.wasm 5.1.4 | **Does not exist** ("Option not found"). Native 9.0.2 ignores `-metadata:s:v rotate=`, which 5.1.4 honours, so no lossless-rotate command runs in both. Versions below; decision **D-024 proposed** (pin everything to 5.1.x, option A). A native 5.1.x build was not run (download not permitted here), so that is the one open verification. |
| 3 | One rotation convention | Done: clockwise degrees everywhere (spec: net displayed rotation measured from content; probe: clockwise display matrix, Python and TS). 12 cases (6 re-encode/metadata, 90 cw, 90 ccw, 180, copy; 1 wasm-only). `hevc_rot90` now probes as 270. |
| 4 | Unsupported tasks | Done: u01-u03 `families = []`, `nearest_supported: null` (schema field added; empty list allowed only for unsupported). |
| 5 | Image-sequence counting | Rule in `training/config.py` and spec schema; explicit counts exact; s19=2 s/5, s20=1 s/10, m03=1 s/5. 9 cases incl. the fps-vs-select boundary. |
| 6 | s27/s30; drop m05 | See below. m05 dropped; 49 tasks carried over. |
| 7 | Tolerances documented | Done in `training/config.py`, with measurements (below). |
| 8 | New tasks, then B0/1.7B/X1 | Waiting for you. Procedure below. |

## FFmpeg versions
| Runtime | Version | `-display_rotation` | `-metadata:s:v rotate=` | frame counts (4 s clip, 1 per 3 s) |
|---|---|---|---|---|
| Native (this machine; training/eval) | 9.0.2 | works | ignored | fps 1, select 2 |
| Browser ffmpeg.wasm core-mt 0.12.10 | **5.1.4** | **Option not found** | works (ccw 90 -> displaymatrix 90.00) | fps 1, select 2 |
Also: FFmpeg 9 removed `-vsync` (`-fps_mode` exists in both). Raw data: `wasm-ffmpeg-capabilities.json`.

## Why s27 and s30 are missing
They never existed. The task file was written once (single commit, `a621191`) and neither id appears in the generator script or anywhere else in the repo or history; numbering simply skipped a number after the F9 block (s25, s26) and after the F10 block (s28, s29). It looks like a third task per family was planned for F9 and F10 and not written, but nothing records that, so treat it as a numbering gap, not removed tasks. Ids are kept stable (no renumbering); new tasks use `n01..`.

## Measured evidence for the tolerances
- **Offset (+-40 ms):** requests of -500 / +300 / +200 ms read -521.3 / +278.7 / +178.7 ms; all 21.3 ms early = one AAC frame of encoder priming.
- **Loudness (+-2 LU):** -16 LUFS request reads -16.0; +20 dB on a -61.8 LUFS clip reads -41.8.
- **Implicit duration (+-0.1 s):** largest deviation over 17 non-offset reference solutions is 0.008 s; the s07 failure mode is 3.9 s off.
- Reference solutions: **43/43 pass** checker v1.2 (`reference-verification.json`; the other 6 tasks are ambiguous/unsupported).

## Tests
Python 470 passed, 2 skipped (new: `tests/env/test_checker_cases.py` 32 golden cases, `tests/tasks/test_spike_v1.py` 97), vitest 71, e2e 5 (incl. the new `ffmpeg-version.spec.ts`).

## Adding your new tasks (item 8)
1. Register clips: `uv run python -m training.corpus.add_clip ~/path/clip.mp4 --id my_clip --licence "own recording" --source "owner"`.
2. Append tasks to `data/tasks/dev/spike-v1.jsonl`: ids `n01..`, `"source": "spike-v1-new"`, `"split": "dev"`, same fields as the originals (see `spike-v1.CHANGES.md`; copy a similar task). Rotation is clockwise (90 right, 270 left); image sequences need `interval_s` and `expected_count`; unsupported tasks use `families: []` and `nearest_supported`.
3. `uv run python -m eval.verify_tasks data/tasks/dev/spike-v1.jsonl` must say all reference solutions pass, and `uv run pytest tests/tasks/test_spike_v1.py` must be green.
4. Tell me; I then run B0 (frozen), base 1.7B and X1 (about $0.03 DeepSeek) and report Wilson intervals for original, new and all.
Caveat: the new clips are not regenerable; they live untracked in `data/corpus` and are only in the manifest.
