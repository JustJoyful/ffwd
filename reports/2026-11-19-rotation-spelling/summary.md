# Which lossless-rotation spelling works? (19 Nov 2026)

Same input (`h264_aac_1080p.mp4`, stream copy), native FFmpeg 5.1.1-static (the pin, `native-5.1.1.json`) and ffmpeg.wasm core-mt 0.12.10 = FFmpeg 5.1.4 in headless Chromium (`wasm-5.1.4.json`, spec `spikes/browser/e2e/rotation-spelling.spec.ts`). "ccw matrix" is the display-matrix angle FFmpeg prints (counterclockwise).

| spelling | native 5.1.1 | wasm 5.1.4 |
|---|---|---|
| `-display_rotation 90 -i ...` | exit 1, `Unrecognized option 'display_rotation'` | exit 1, `Error splitting the argument list: Option not found` |
| `-metadata:s:v:0 rotate=0` | ok, no matrix | ok, no matrix |
| `-metadata:s:v:0 rotate=90` | ok, ccw 90 | ok, ccw 90 |
| `-metadata:s:v:0 rotate=180` | ok, ccw 180 | ok, ccw -180 (same orientation; printing convention) |
| `-metadata:s:v:0 rotate=270` | ok, ccw -90 | ok, ccw -90 |

**Result:** `-display_rotation` fails on both runtimes; `-metadata:s:v:0 rotate=<ccw degrees>` works on both with the same orientation. rotate=N is counterclockwise: our one convention is clockwise degrees (spec.schema.json), so the reference for "rotate R clockwise" is `rotate=(360-R) mod 360`.

## What changed (protocol 0.2.0 -> 0.3.0)
- `packages/protocol/allowlist.json`: `-display_rotation` removed (allowlist v0.2.0). The working option needed no new entry: `-metadata` (kind `metadata`, `key=value`) already accepts `rotate=N` in both validators; the conformance file now pins it.
- `validator.jsonl`: the old "lossless rotate metadata" case (which used `-display_rotation`) is replaced by `rotate=90/180/270` accepted and a case that `-display_rotation` is rejected (`option not allowed: -display_rotation`), run by both the Python and the TS validator.
- Python + TS: `PROTOCOL_VERSION` 0.3.0 (`training/config.py`, `spikes/browser/src/config.ts`, test), the five schema `$id`s.
- Reference runs for lossless F5 (`training/taskgen/frag.py`) emit only the tested spelling; the `LOSSLESS_ROTATE_SPELLING` switch and the dead branch are removed.
- Frozen B0 still emits `-display_rotation`: it is now **rejected by the validator** instead of failing inside FFmpeg (same outcome, earlier). Not patched; reported in the B0 re-run.

## Found on the way (browser probe parity)
The TS probe test (every corpus clip's `ffmpeg -i` log parsed in the browser vs the Python probe) had been failing since corpus v1 (10 clips had no wasm log); my ingest made it 27. Captured all 39 logs with `e2e/capture-i-logs.spec.ts` and the parity test then found two real differences, both fixed: (1) VP8 webm logs `30k fps, 60 tbr`, the TS parser now falls back to `tbr` like Python's `stream_fps`; (2) 14 stored probes came from the system 9.0.2 `ffprobe` and differ by up to 0.05 s in duration from the pinned build and from wasm; `ingest_sources --reprobe` refreshed them with the pinned ffprobe (one build's numbers only, D-029).
