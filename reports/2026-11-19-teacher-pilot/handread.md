# Hand-read notes (read by Claude, 19 Nov 2026; trajectories in `trajectories.jsonl`)
Read in full: F2 tr-004bb8532b-casua, F3 tr-18b9f8d191-polit, F5 tr-06efb1d23f-sympt, F6 tr-00106df56b-polit, F7 tr-00e7c56c8f-casua, F8 tr-04de361088-casua, F11 tr-00f54427ff-casua, unsupported tr-01663c536d-casua, F12+F1+F5 tr-005351acbb-sympt, F3+F4+F1+F12 tr-01500155b9-terse; failure: F6 (ambiguous) tr-009e63bcd1-casua.
- F2 merge: concat filter, spec sums the durations; fine.
- F3 iPhone to PowerPoint: HEVC -> H.264/AAC mp4, same size/fps; fine.
- F5 "turn left 90": spec rotation 270 (clockwise convention) correct; first run `rotate=270` (turns right) failed the check (actual 90), second `rotate=90` passed. Container string copied from the probe in the first spec -> invalid action.
- F6 "under 1 MB, keep 800p": bitrate 900k + 96k audio, passed first try.
- F7 jpg every 2 s: `fps=1/2`, expected_count 2 on a 4 s clip; fine.
- F8 gif 320 wide: first spec had `height: -2` (invalid), retried with 320x180; the run used `scale=320:-2`.
- F11 audio 100 ms earlier: first `-itsoffset -0.1` before the first `-i` shifted the video input (measured +78.7 ms), fixed by moving it before the second `-i`; container string copied -> one invalid action.
- unsupported: correct refusal; `nearest_supported: "F4"` is wrong (gold null).
- F12+F1+F5: `-ss 0 -t 1` before `-i` with `setpts=PTS/0.5` gives 2 s; transpose=2 for "left" (re-encode, request did not ask for lossless); fine.
- F3+F4+F1+F12: last 1 s of a 4 s webm at 3.008 s, square crop 1080x1080, 60 fps; fine.
- Failure (ambiguous "make it smlaler"): spec + 2 runs guessing 3 MB (harness: "no executable outputs"), then ask_user; must ask first.
