# PRD: ffwd

| | |
|---|---|
| **Owner** | Joydeep Das (GitHub: JustJoyful) |
| **Status** | Approved for Phase 0 |
| **Last updated** | 14 Nov 2026 |
| **Related** | ARCHITECTURE.md · EVALUATION.md · PHASES.md · DECISIONS.md |

---

## 1. Summary

ffwd is a free, open-source website for **occasional video chores**. You drop in a file, describe what you want in one sentence, and a small AI agent running **on your own computer** writes the FFmpeg commands, runs them, **checks the result against your request**, and fixes the command if needed. Nothing is uploaded and there's nothing to install. Big files and batches can be handed off to an optional local helper app.

## 2. Problem

There is a **long tail of video chores**: each one is needed only now and then by any single person, but lots of people need them in total. For example:

- Take a frame every 2 seconds and save the frames as images.
- The iPhone video won't play in PowerPoint or on the TV; fix it.
- The audio is half a second behind the video.
- Merge these 12 clips into one.
- Rotate this without losing quality.
- Make the quiet audio louder.
- Cut the first 3 seconds off all 40 of these files.

**What people do today, and why it hurts:**

| Current option | Pain |
|---|---|
| Search online → find an FFmpeg command / ask ChatGPT | Then stuck **installing FFmpeg and using a terminal** (especially painful on Windows); commands often ignore the actual file or contain invalid flag combinations; nothing checks the result |
| Online converters | Ads, size limits, **uploading private files** to unknown servers |
| GUI apps (e.g. Shutter Encoder, HandBrake) | Can do much of this, but you must know **which menu holds the option** |
| Full editors (CapCut, Premiere, DaVinci) | Overkill for a 10-second chore; steep learning curve |
| Coding agents (Claude Code, Codex) | Excellent at this, but only for people who use a terminal and pay for a subscription |

## 3. Target users

**Primary:** non-developers who hit a video chore **a few times a month**, on a desktop or laptop.

| Persona | Typical chores |
|---|---|
| **Students & teachers** making presentations | iPhone video won't play in PowerPoint, trim a lecture clip, extract frames for slides, merge clips |
| **Small creators** | crop to vertical, size-limited exports, GIFs, loudness fixes, batch trims |
| **Researchers / lab users** handling recordings | extract frames at intervals, convert formats, fix audio offset, batch processing |

**Not targeted in v1:**
- Developers who already use Claude Code/Codex (we don't claim to beat them for this audience)
- Professional editors who need timelines, effects and colour grading
- Mobile users (v1 is desktop/laptop only; see §11)

## 4. Positioning

**Pitch:** *"Describe an odd video chore in one sentence. It runs on your machine with nothing to install, nothing uploaded, and the result checked."*

**Honest competitive picture (checked Nov 2026):**

| Alternative | What it does | Our difference |
|---|---|---|
| NL→FFmpeg wrappers (LLMPEG, wtffmpeg, ai-ffmpeg-cli, MediaLLM) | CLI tools calling an LLM | Need a terminal and FFmpeg installed; no output verification |
| vidmix.app | In-browser ffmpeg.wasm + DeepSeek API | Cloud LLM; no output checking |
| Ez FFmpeg | **Regex** patterns for ~20 common operations | No AI: fails on unusual phrasing, multi-step and file-dependent requests |
| ELLMPEG (2026 paper) | Retrieval + self-reflection with untrained models | Research system, not a product; no training |
| Frontier coding agents | Solve these well | Terminal + subscription; not for our users |

**Our real differentiators:**
1. **Nothing to install, nothing uploaded:** model and FFmpeg run in the browser tab.
2. **Verified results:** every output is checked against a spec the user confirmed.
3. **File-aware:** the agent probes the actual input (duration, codecs, bitrate) before acting.
4. **Free at any scale:** each user brings their own compute, so our cost per edit is ~0.

**Expectation setting:** this is an **occasional-use utility**. Expect modest numbers and people coming back **about once a month**, not daily.

## 5. v1 scope: chore families

| # | Family | Example request | Mode |
|---|---|---|---|
| F1 | Trim / cut | "cut the first 3 seconds" · "keep 0:12–0:40" | Browser (batch: helper or small-file batch in browser) |
| F2 | Merge / concatenate | "merge these 12 clips into one" | Browser (small) / Helper |
| F3 | Compatibility convert | "iPhone video won't play in PowerPoint/on the TV" (HEVC/MOV → H.264/AAC MP4) | Browser* |
| F4 | Resize / crop | "make it vertical 9:16" · "720p" | Browser |
| F5 | Rotate / flip | "rotate 90° without losing quality" (metadata/lossless where possible) | Browser |
| F6 | Compress to size | "under 10 MB" | Browser |
| F7 | Extract frames | "a frame every 2 seconds as images" | Browser |
| F8 | GIF | "make a GIF of 0:05–0:09" | Browser |
| F9 | Audio extract / remove | "save the audio as MP3" · "remove the sound" | Browser |
| F10 | Volume / loudness | "make the quiet audio louder" | Browser |
| F11 | A/V sync offset | "audio is half a second behind" | Browser |
| F12 | Speed / FPS | "2× speed" · "convert to 30 fps" | Browser |

\* F3 depends on HEVC decoding in the ffmpeg.wasm build, which is a **Phase 0 blocking check**. If the browser can't decode HEVC, F3 becomes helper-only and the UI must say so clearly.

Multi-step requests that combine 2–4 families (e.g. "trim 0:12–0:40, make it vertical and under 10 MB") are **in scope** and are where the AI matters most.

## 6. Out of scope (v1)

- Mobile browsers (desktop/laptop only)
- Burned-in subtitles (font handling in wasm; consider for v2)
- Content-aware edits: object removal, "find the best moments", auto-captions, AI upscaling
- Timeline editing UI, effects, colour grading
- Accounts, cloud storage, sharing links
- Non-English requests (log them as unsupported; consider later)

## 7. User experience flow

1. **Land** on the homepage (or a per-chore landing page with the request pre-filled).
2. **Capability check:** WebGPU present? RAM/GPU adequate? If not, show the system requirements and offer the helper app.
3. **Model loads** (first visit: one-time download with a progress bar; later visits load from cache).
4. **Drop file(s)**; the agent probes them.
5. **Type the request.**
6. The agent proposes a **plain-language spec**: *"Output: MP4, 0:12–0:40, 1080×1920, ≤10 MB. OK?"*. The user confirms or edits.
   - If the request is ambiguous → the agent **asks one clarifying question** (`ask_user`).
   - If the request is out of scope → the agent says so plainly (`unsupported`) and suggests the nearest supported chore.
7. **Run** with a progress bar; on failure, the agent retries within its turn budget (≤4 runs).
8. **Result:** preview, check summary ("✓ 1080×1920 ✓ 0:28 long ✓ 9.4 MB"), download / save to folder. "Show the FFmpeg command" is available for curious users.
9. Big file or batch detected → offer the **helper app** handoff.

## 8. Functional requirements

| ID | Requirement |
|---|---|
| FR-1 | Accept one or more local files via drag-and-drop or picker; folder selection for batches where the browser supports it |
| FR-2 | Probe inputs (duration, streams, codecs, resolution, rotation, bitrate, size) before planning |
| FR-3 | Convert a request into a spec; show it to the user in plain language; allow edits before running |
| FR-4 | Execute only allowlisted FFmpeg operations via structured arguments |
| FR-5 | Verify every output against the confirmed spec; show which checks passed or failed |
| FR-6 | Retry automatically on error or failed check, up to the turn budget; then explain the failure honestly |
| FR-7 | Support `ask_user` (one clarifying question) and `unsupported` (honest refusal + nearest alternative) |
| FR-8 | Provide preview + download; batch results saved to a user-chosen folder or as a zip |
| FR-9 | Detect the local helper and offer handoff for large files, batches and GPU encoding |
| FR-10 | Show an optional "view FFmpeg command" panel |
| FR-11 | Per-chore landing pages that open the tool with a pre-filled request |
| FR-12 | Anonymous analytics as specified in §10; a plain-language privacy page |

## 9. Non-functional requirements

| Area | Requirement |
|---|---|
| **Privacy** | Media never leaves the device. Analytics never include prompts, file names, paths, contents or IP. |
| **Security** | No shell execution anywhere. Helper accepts only paired requests from the official origin, on loopback only. |
| **Performance** | Targets set from Phase 0 measurements (model load time, ms/token, seconds per typical chore), then tracked in CI/benchmarks |
| **Reliability** | A failed or partial edit is never reported as success. Output files are written only after the check passes, or clearly marked as failed. |
| **Accessibility** | Keyboard navigable; readable contrast; progress announced to screen readers (basic level) |
| **Openness** | Code, task generator, evaluation harness and model weights are public; the README includes honest limitations |

## 10. Success metrics

### 10.1 Product metrics (PostHog, anonymous)
- **Activated users:** browser IDs with ≥1 edit that **passed its check**. This is the headline "users" number.
- **Returning users:** activated IDs that complete another successful edit in a **later 30-day window**. Report "% returning within 30 / 60 days" and monthly actives.
- **Funnel:** visit → capability OK → model loaded → first edit started → spec confirmed → edit succeeded → returned.
- **Success rate by chore family**, and **unsupported-request log by category** (this drives the roadmap).
- **Model load drop-off:** the share of visitors who leave during the model download (drives the decision between the 0.6B and 1.7B models).

### 10.2 Model / research metrics
Defined in EVALUATION.md: task success on held-out chores, spec-extraction accuracy, turns per task, unnecessary re-encode rate, invalid-command rate, seconds per edit (browser vs native), cost per task vs frontier.

### 10.3 Targets
Set after Phase 0 baselines exist. **Don't invent targets before measuring.**

## 11. System requirements (v1, provisional; finalised in Phase 0)

- Desktop or laptop; recent **Chrome or Edge** (primary). Firefox and Safari are best-effort, after testing.
- **WebGPU** available.
- RAM and GPU memory thresholds to be measured in Phase 0 for the 0.6B and 1.7B models (expected: ≥8 GB system RAM).
- Browser-mode file size limit: set from Phase 0 memory tests; larger files go to the helper.
- Helper app: Windows first, then Linux, then macOS.

## 12. Distribution plan

These users **search online for their exact problem**, so:
1. **One landing page per chore** ("Extract a frame every 2 seconds, no install, no upload") that opens the tool pre-filled. This targets long-tail search.
2. **Answer real questions** where people ask them (Reddit, Super User, Video Production Stack Exchange) with a working link, following each community's self-promotion rules.
3. **Launch posts** once ~20 chores work reliably: Show HN, relevant subreddits, Indian student/creator communities, college groups.
4. A **demo video** (60–90 s) showing three chores end to end.
5. Track referrers in PostHog (anonymous) to learn which channel produces activated users.

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| ffmpeg.wasm can't decode iPhone HEVC | Phase 0 blocking check; fallback to helper for F3 with clear UI messaging |
| Model download too large → drop-off | Measure in funnel; ship 0.6B by default; cache aggressively |
| Small model too weak even after training | Phase 0 go/no-go gap check; presets/regex fallback for the most common chores |
| RL adds little over SFT | Report honestly as a finding; ablations planned (EVALUATION.md) |
| Model grades its own work leniently at runtime | User-confirmed spec; checker is deterministic code, not the model |
| Browser memory crashes on large files | Size limits from Phase 0; helper handoff |
| Platform/upload limits change (Discord etc.) | No hard-coded platform presets without a dated source; verify before shipping presets |
| Teacher API terms change | Record teacher and terms date in the data card; fallback = rejection sampling |
| Low adoption | Per-chore pages + answering real questions; measure channels; accept modest numbers as normal for this kind of tool |

## 14. Open questions

- Final product name and domain
- 0.6B vs 1.7B as default (decide from funnel + accuracy)
- Exact platform presets and their dated sources
- Helper packaging per OS
- Whether to accept Hinglish requests in v2
