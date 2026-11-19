# Phase 1 status (autonomous run; owner away from 16 Nov 2026)

Plan: `docs/superpowers/plans/2026-11-16-phase-1-core-model.md`. Rule while the owner is away: do every ungated task; **never cross an [ASK] gate**
(DeepSeek spend incl. paraphrases/teacher/X1, the main GRPO run + shuffled control, the single test run, publishing beyond private repos).
No questions to the owner; conservative defaults, documented. All work is on `main` (commits tagged by task).

## Done (code + tests, all ungated)
| Task | What |
|---|---|
| T1 | protocol 0.2.0, split-purpose guard (`training/taskgen/loader.py`): training code cannot read test splits |
| T2 | fail-closed bubblewrap sandbox option, rollout timeouts. **FFmpeg pin blocked on D-024** |
| T3 | corpus v1 (22 clips: VFR, 4:3, ProRes, MKV, mono/44k, noisy, known A/V offsets, rot270), tags, hash-verified Hub distribution code. **Hub push not done** (creates a repo on your account) |
| T4 | checker v1.3: quality floor (SSIM/PSNR) for size targets; 6 golden cases |
| T6 | D-026: ONE agent chat template (empty think on every assistant turn; stock Qwen3 drops it from history, which would skew train vs inference); spec-first prompt v1 (DRAFT hash until D-024); `require_spec` loop option. Verified identical in HF, Jinja and llama.cpp |
| T7-T10 | task generator v1: F1-F12 samplers on a shared plan, compositions of 2-4 families, ambiguous/unsupported tasks, 5 train + 2 held-out styles, content-hash splits, held-out family combos, executed-reference verification, parallel build + manifest |
| T11 | leakage audit (`eval/leakage.py`). **Train paraphrases via DeepSeek not run (gated)** |
| T12 | test-run lock (`eval/testlock.py`), Phase 1 preregistration as a DRAFT |
| T13 | teacher runner + data card (train-only, spec-first, passing-only, off-peak gate, refuses draft prompt). **Pilot/bulk gated** |
| T15 | rejection sampling code (free local model) |
| T16 | SFT dataset/mix/validation split, LoRA SFT trainer, build CLI (code only; not trained) |
| T17 | lockstep batched rollouts + HF batched generator (verified equal to one-at-a-time under padding) |
| T18/T19 | stop rules (`training/grpo/gates.py`), main GRPO driver (`training/grpo/main_run.py`); **never run: gated** |
| T22 | parity metrics (`eval/parity.py`); GGUF export needs llama.cpp's converter script (not fetched: external code) |
| T23 | `ffmpeg-agent` CLI + plain-language spec describer + goldens |
| T24/T25 | results report builder (Holm, denominators, test-lock checks), model/data card builders, licence audit |
| extra | D-032 proposal: free programmatic "oracle" trajectories (`training/teacher/oracle.py`) |

## Smoke tests run (local RTX 3050, free, tiny; NOT the gated runs)
- Task build v1 finished: 4486 train / 300 dev / 500 test-iid / 200 test-compositional / 200 test-phrasing (`reports/2026-11-16-taskgen-v1/`): held-out splits pass the leakage gate (max Jaccard 0.69 / 0.74 < 0.9). Limitations there (single-family content space is small; few ambiguous/unsupported dev tasks).
- Oracle trajectories: 60/60 train tasks solved through the real spec-first loop (draft prompt). SFT examples are ~1.6k tokens each (only ~220 trained): `SFT_MAX_LEN` raised to 3072; default batch 2 x 8.
- SFT: 3 steps on the local GPU ran (eval loss 0.705), adapter saved, merged model carries the agent template (`tests/export`).
- GRPO driver: 1 step, 2 generations x 2 prompts, real lockstep generation + telemetry + checkpoint: works (0.013 GPU-h; junk policy, as expected after 3 SFT steps).
- GGUF export: **blocked** on llama.cpp's `convert_hf_to_gguf.py` (not in the release binaries; fetching it means running external code). Wrapper is ready: set `LLAMA_CPP_DIR` / `LLAMA_QUANTIZE`.

## Kaggle kill-and-resume: failed at secrets (needs one UI step from you)
The pushed kernel `justjoyful/ffmpeg-agent-resume-auto` waited ~2 h in the GPU queue, then died after 1 s: `kaggle_secrets.get_secret('HF_TOKEN')` -> HTTP 400.
Kernels pushed from the CLI have no secrets attached, and I will not embed tokens in pushed code. **Owner step:** open https://www.kaggle.com/code/justjoyful/ffmpeg-agent-resume-auto -> Add-ons -> Secrets -> tick `HF_TOKEN` and `GITHUB_TOKEN`. Then either re-run
`uv run python -m training.grpo.kaggle_kernel push --mode train` (I can do this on the next wakeup once told) or click Save & Run. The log is in `reports/2026-11-16-phase1-dev-baselines/kaggle-session1-error.log`. D-022's Kaggle verification stays open.

## Waiting on the owner
1. **G0:** Kaggle kill-and-resume result (kernel `justjoyful/ffmpeg-agent-resume-auto` still QUEUED), D-024 FFmpeg pin decision, D-025-D-031 proposals in the plan, D-032, your ~20 new spike-v1 tasks + 2-3 clips.
2. **G-terms:** read DeepSeek's terms (training on outputs) and send the off-peak window (`config.DEEPSEEK_OFFPEAK_UTC`, `TEACHER_TERMS_URL`).
3. **G1/G2:** approve the teacher pilot (<= $0.05) then bulk (<= $2.30); approve the paraphrase spend (<= $0.30).
4. **G3:** approve the shuffled-reward control and the main GRPO run (<= 15 GPU-h).
5. **G4:** preregistration FINAL + the single test run. Your ~10 own clips + ~100 test-real requests.
6. Freeze prompt v1 (set `SYSTEM_PROMPT_V1_SHA256`) after D-024.

## Not done / blocked
- Real SFT, M1, GRPO: need data (gated) and a GPU (Kaggle queued; local RTX 3050 is for smoke tests only).
- B0 v2 (patterns from train phrasing only) and dev baselines on the new splits.
- Dual-runtime (ffmpeg.wasm) conformance run: Phase 2.


## Kaggle retry after owner attached secrets (22:20 IST)
Pushed `--mode train` as kernel version 2. It failed the same way: `get_secret('HF_TOKEN')` -> HTTP 400 (`reports/2026-11-16-phase1-dev-baselines/kaggle-session2-error.log`). Secrets attached in the UI are not reaching API-pushed runs. Not re-pushed again. Next step needs the owner: in the kernel's UI (Add-ons > Secrets) tick the HF_TOKEN toggle for the latest version and run it from the UI, or tell me to use another method.


## Dev baselines on dev v1 (n=300), finished 23:08 IST
B0 regex 158/300 = 53% [47%, 58%]; B2 stock Qwen3-0.6B 0/300 = 0% (all 8 turns invalid: writes `{"spec":...}` without `"action"`). Details and Wilson tables by difficulty: `reports/2026-11-16-phase1-dev-baselines/summary.md`.


## Kaggle kill-and-resume: PASSED on the Hub evidence (23:56 IST)
Owner ran session 1 (checkpoints 2, 4 on `JustJoyful/ffmpeg-agent-ckpt`), then re-ran with `MODE='resume'` (after the clone fix + clearing `/kaggle/working/ckpt`). `checkpoint-6` and `-8` appeared; in `checkpoint-8` the `log_history` and `toy_metrics.jsonl` steps 1-4 are identical to `checkpoint-4`, steps 5-8 continue, LR 6.25e-06 -> 5e-06 across the boundary. Recorded in D-022. Still unconfirmed: the notebook's `verify_resume` line (`"ok": true`) and that local ckpt was empty; owner can paste the log tail to close both.


### Kaggle resume: `verify_resume` confirmed (17 Nov)
Owner pasted the console output: `"ok": true`, `"problems": []`, `"steps": [1,2,3,4,5,6,7,8]`, exit code 0. Kill-and-resume is closed (D-022 updated). Only the "local ckpt dir was empty" detail rests on the notebook edit rather than a log line.


## Owner plan review applied (17 Nov, after the Kaggle test)
Done: D-027 (change a: held-out style `technical` -> `context_first`; change b: real clips split by clip, `add_clip --role` required, CI test with a planted violation), D-028 to D-031 recorded as approved, D-024 marked accepted (option A) from the D-029 wording, preregistration edits (Q7 = one pooled comparison on test-real + test-phrasing, per-family descriptive only; detectable-difference table; M1 >= 90% "SFT nearly sufficient" rule; kept-rate gate rule proposed, number set after the X1 dev run), plan edits (G0a blocks T16+ only, T4 Step 4 reworded, status table), `PHASES.md` and `CLAUDE.md` set to in progress. `reports/TEST_RUNS.jsonl` does not exist: no test split has ever been run, so changing test-phrasing wording invalidates nothing.

**Blocked, needs the owner (D-024/D-029 pin):** I downloaded the 5.1.1 static build (sha256 `2d848c37...9f42`, `~/.cache/ffmpeg-pin-dl/ffmpeg-5.1.1-amd64-static.tar.xz`) but the sandbox classifier denied extracting and running it, as last time. Please run in this session: `! cd ~/.cache/ffmpeg-pin-dl && mkdir -p x && tar -xf ffmpeg-5.1.1-amd64-static.tar.xz -C x && x/ffmpeg-5.1.1-amd64-static/ffmpeg -version | head -1`. If runs of that binary are still refused for me, add a Bash permission rule for it. Until then: no pin enforcement, no split rebuild (the test-phrasing file still holds the old `technical` wording; it is rebuilt once, together with the pin, to avoid regenerating twice), `LOSSLESS_ROTATE_SPELLING` unchanged.

**Still waiting on the owner:** D-032 decision (text pasted in the reply), DeepSeek terms snapshot + off-peak window (nothing paid runs until the terms file exists), at least 10 own clips with `--role`, about 100 test-real requests.


## Owner decisions applied (17 Nov, second review) and the pin hand-off
- **D-024 confirmed, option A.** No static linux 5.1.4 exists (publisher's `old-releases/` has 5.0.1, 5.1.1, 6.0), so the pin stays **5.1.1**; the gap to the browser's 5.1.4 is recorded in D-024 and covered by a parity test still to be written (every conformance case on native 5.1.1 and ffmpeg.wasm 5.1.4, compare checker results).
- **Built now (committed):** `training/env/ffmpeg_pin.py` (installer that verifies the pinned sha256 and extracts with the tar `data` filter, never runs the binary; fail-closed `require_pinned`, wired into the executor, checker, quality, orientation and probe), pin constants in `training/config.py`, Kaggle script, notebook and CI now install the pinned build instead of apt's. **Enforcement is staged**: `FFMPEG_PIN_ENFORCED = False` until the binary has been run here once; it must be True before any Phase 1 data is built.
- **Your step (after you verify the publisher's checksum):** `! cd ~/Projects/ffmpeg-agent && uv run python -m training.env.ffmpeg_pin install --tarball ~/.cache/ffmpeg-pin-dl/ffmpeg-5.1.1-amd64-static.tar.xz` (checks our pinned sha256, extracts to `~/.cache/ffmpeg-agent/pin/`), then `! ~/.cache/ffmpeg-agent/pin/ffmpeg-5.1.1-amd64-static/ffmpeg -version | head -1`.
- **Then I do, in order:** flip `FFMPEG_PIN_ENFORCED`; switch `LOSSLESS_ROTATE_SPELLING` and the rotated corpus-clip recipes to the 5.1 metadata spelling (and check the allowlist/validator accept it); run the whole suite on 5.1.1 and fix what differs; rebuild all splits once (also picks up `context_first`); diff the per-split sha256 against the old manifest; re-run B0 on dev v1 into a fresh report dir (the frozen B0 emits `-display_rotation`: any change in its score is reported and explained, not patched); leakage audit on the new test-phrasing/test-compositional; write the native-vs-wasm parity test.
- **D-032 approved** (cap 30%, `source=oracle`, fallback with explicit flag, M1-oracle dev-only ablation refused on test splits by `eval/testlock.py`). **Peak windows** are in `config.DEEPSEEK_PEAK_UTC` (01-04, 06-10 UTC); the bulk gate now refuses during peak.
- **Teacher pilot (G1, <= $0.05) is approved but not started:** `training/teacher/terms/2026-11-17/` does not exist yet, and `config.TEACHER_TERMS_URL` / `TEACHER_TERMS_SNAPSHOT_SHA256` are still `None`. When the files are there I set both from them and then the pilot can run. The X1 dev run (<= $0.05) follows the same condition, then the kept-rate gate number goes into the preregistration.

## Proposal (NOT started): build FFmpeg 5.1.4 for exact browser-version parity (19 Nov 2026)
Needed before: the teacher bulk run (G2). Owner asked to propose, not start.

**Why / how much it buys.** The browser runs ffmpeg.wasm core-mt 0.12.10 = FFmpeg 5.1.4; the pin is 5.1.1 (no static 5.1.4 exists). 5.1.2-5.1.4 are bug-fix/security releases. After the pin went active, the whole suite and every conformance case pass on 5.1.1 (the differences found were 9.x-vs-5.1, not 5.1.1-vs-5.1.4), so I expect little behavioural gap. Still, a self-built 5.1.4 makes "same FFmpeg core version in browser and native" literally true.

**Source and trust.** `https://ffmpeg.org/releases/ffmpeg-5.1.4.tar.xz` + its `.asc`, checked with `gpg --verify` against the FFmpeg release signing key. The key fingerprint must be compared with the one printed on ffmpeg.org/download.html (I will not take it from memory). Trust root = ffmpeg.org's key for the source, plus our own sha256 of the resulting artifact (the same pin mechanism as today, new url/sha256/version string).

**Configure flags** (derived from `packages/protocol/allowlist.json`: encoders libx264, libx265, libvpx (vp8+vp9), mpeg4, gif, png, mjpeg, aac, libmp3lame, libopus, libvorbis, flac, pcm_s16le; every listed filter, `loudnorm`, `ebur128`, `palettegen`, `concat`, `select`, ..., is built in; reference solutions actually use libx264, aac, libmp3lame, copy):
```
./configure --prefix="$PWD/out" --enable-gpl --enable-static --disable-shared \
  --disable-autodetect --enable-zlib \
  --enable-libx264 --enable-libx265 --enable-libvpx --enable-libmp3lame --enable-libopus --enable-libvorbis \
  --disable-debug --disable-doc --disable-ffplay --disable-indevs --disable-outdevs --disable-network \
  --pkg-config-flags=--static --extra-ldflags=-static
```
`--disable-autodetect` stops accidental links (xcb, vaapi, alsa, sdl); `--disable-network` matches the allowlist (protocols are rejected anyway). Not needed because the allowlist has no filter for them: libass/freetype/fribidi/harfbuzz (subtitles, drawtext), zimg (zscale), libwebp, libtheora (all present in the ffmpeg.wasm build, none reachable). Dependencies built static first, each pinned by version + sha256: x264 (stable branch commit), x265 3.5, libvpx 1.13, lame 3.100, opus 1.4, libogg + libvorbis. The wasm core's own `-buildconf` should be read in the browser spike to confirm the above is a superset of what the allowlist needs (not yet done).

**Effort** (~1 working day, ~3 h of it waiting on compiles): key + source verification 0.5 h; static dependency builds 2 h (x265 is the fiddly one: cmake, 8/10/12-bit); FFmpeg configure + compile 0.5 h (10-15 min on 12 cores); static-link debugging 1-2 h; full suite + conformance on the new binary, diffed against 5.1.1 results, 1 h; package, upload (private HF dataset or a GitHub release), switch the pin (`config.FFMPEG_PIN` url/sha256/version, tests, Kaggle/CI install) 1 h; D-024 and docs 0.5 h. **Blocker: disk.** A build needs about 4 GB; `/home` has 1.6 GB free. Options: free space (e.g. old `data/jobs/*` baseline job dirs, 1.3 GB, owner's call), or build in GitHub Actions / Kaggle and publish the artifact (also gives a reproducible recipe in CI).

**Risks / limits.**
1. A self-built binary has no publisher signature either; builds are not guaranteed bit-reproducible (record gcc version and flags in the build manifest).
2. Even 5.1.4 native is not identical to wasm: different codec-library versions, SIMD/asm paths and float math (loudnorm, encoders). Checks use tolerances, not bit-exactness, but the native-vs-wasm **parity test is still required** whatever we build.
3. Distributing a GPL binary (Phase 3 helper) needs the corresponding source offer; the repo is GPL-3.0 (D-016), so this is fine but must be written down.

**Recommendation.** Write and run the parity test first (every conformance case on native 5.1.1 and ffmpeg.wasm 5.1.4, checker results compared). If it passes, the 5.1.1 pin is enough for Phase 1 and the 5.1.4 build can wait until Phase 3 (helper distribution), where a reproducible CI build is wanted anyway. Build 5.1.4 now only if the parity test finds a patch-level difference or you want the exact-version claim before G2.

## 19 Nov 2026 (evening): pin active, protocol 0.3.0, splits final, prompt frozen, pilot done, STOPPED at the pilot gate
- Commits: f175332 corpus ingest, 9046422 pin + rebuild, 8f68b9e protocol 0.3.0, 912fe29 final splits, e19b88b terms snapshot, e8c32c0 prompt freeze (D-034), 5831cc1 pilot + X1 dev, 9ef5543 decoder-thread cap + parity.
- Splits (final, seed 20261115, FFmpeg 5.1.1-static): train 4472 / dev 300 / test-iid 500 / test-compositional 200 / test-phrasing 200 (`reports/2026-11-19-taskgen-v1-final/`). New test-real clips change no split.
- Native 5.1.1 vs ffmpeg.wasm 5.1.4: 48/48 conformance recipes at parity; the 5.1.4 build is not needed for Phase 1 (`reports/2026-11-19-parity-.../run4-fresh-build`).
- Teacher: terms snapshot taken and pinned; prompt v1 frozen; X1 dev 58/60 (gate 82%); pilot 19/20 kept, cache-hit 84%, $0.0125. **Stopped before bulk: the 10-trajectory hand-read found (1) invalid-action turns in 5/19 kept trajectories (SFT now drops them) and (2) a wrong `nearest_supported` that the scorer does not check (owner decision a/b/c, see `reports/2026-11-19-teacher-pilot/summary.md`).**
- Spend: $0.112 of $4. Not done / waiting: owner decision on the pilot findings, pricing-page re-check before bulk, Kaggle kill-and-resume confirmation (Hub evidence from 17 Nov shows a clean resume) for SFT on Kaggle, GRPO (G3), test run (G4).

## 20 Nov 2026 (night): bulk teacher done, SFT done, M1 dev eval done, STOPPED before GRPO
- Teacher bulk: 3490 episodes, kept 3199 after the label filter, $2.30, cache-hit 84% (`reports/2026-11-19-teacher-bulk/`). Paraphrases + oracle mix -> 6032 train / 333 val examples (`reports/2026-11-19-sft-data/`). DeepSeek ledger $2.675 of $4.
- SFT 0.6B on Kaggle T4: 2 epochs, 2 x 8 batch, ~5 h, adapter fetched. Final losses were not captured (see the report).
- GGUF path proven (b12032, D-036). **M1 (Q8_0) on final dev: 293/300 = 98% [95%, 99%] vs B0 178/300 = 59%**; 0 invalid turns; all 7 failures are the 4-run limit on multi-family tasks. Dev is in-distribution; leakage check done (`reports/2026-11-20-m1-dev/summary.md`).
- **Waiting for the owner:** G3 (GRPO + shuffled-reward control, <= 15 GPU-h), G4 (preregistration FINAL + the single test run, owner's own clips and ~100 test-real requests). Also open: decision on `remove_object` -> F4 label strictness; whether to run a 1.7B SFT; HF-vs-GGUF parity of M1.

## 20 Nov 2026 (early morning IST): follow-ups 1-6 done; STOPPED before G3
- Parity (`reports/2026-11-20-m1-parity/`): HF fp16 vs GGUF Q8_0, 100 seeded dev tasks, 99/100 agreement, McNemar p=1.0, paired diff +1 pp [0, +3]; transcripts byte-identical on 65% (first turn 86%).
- Dev failures (`reports/2026-11-20-m1-dev-failures/`): 7 model errors, 0 checker false negatives; one generator wording ambiguity (speed-before-trim); F2+F9 (join + remove sound) is the capability gap (0/3).
- Leakage (`reports/2026-11-20-leakage-audit/`): exact-duplicate requests vs train: test-iid 104/500 (20.8%), test-compositional 0/200, test-phrasing 0/200, dev 45/300. test-iid reported on full AND dedup (396) subset (preregistration amended; D-039).
- T18 (`reports/2026-11-20-t18-pass-rates/`): in-band share 3% [2%, 6%] (302-task sample), 6% [3%, 13%] on the 110 never-trained-on train tasks; far below 30%. A difficulty-widened train set is proposed with an estimate, NOT built.
- D-037 (SFT config deviation, Kaggle script fix), D-038 (`unsupported` graded on the action only), D-039 (test-iid dedup reporting). No system was run on any test split; no 1.7B SFT.
- **Waiting for the owner:** G3 (GRPO + shuffled-reward control), G4 (preregistration FINAL + single test run + own clips/test-real requests); Holm-on-full-vs-dedup choice; whether to build the widened train set first; the Kaggle log tail for M1's final losses. The preregistration requires the phrase "SFT nearly sufficient" in the report (M1 dev 98%).
