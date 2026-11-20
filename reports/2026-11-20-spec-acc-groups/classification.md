# 20 groups where `spec_acc` is the only varying reward term: real errors or equivalent alternatives? (20 Nov 2026)

Method: from the 40 tasks whose K=8 group had `spec_acc` as the only varying term in the earlier reward-variance sample, I re-sampled K=8 (M1 Q8_0, T=1.0, prompt v1, specs kept: `widened/`, `t18/`) and kept the groups where it was again the only varying term (27 of 40 reproduced it; 3 had other signal; 10 had none). I read the first 20 by task id (`groups-dump.md` has every emitted spec and its differences from the gold spec). **This is my own reading, not a measurement**; every row is auditable in the dump.

Test applied: would the emitted spec, shown to the user at confirmation, mislead them (it contradicts the request or the output the command produces, or it drops something the user explicitly asked for)? Fields that only over-specify true facts (codec, pix_fmt, input fps, `rotation: 0`), tolerances, family-tag order or an extra family tag, `0` vs `0.0`, and a 1 px rounding are "equivalent": nothing the user would act on. "Variance-creating" means the fields that differ BETWEEN the 8 samples (the only thing that makes `spec_acc` vary inside the group); a real error shared by every sample creates no variance and is listed separately.

## Result

| | groups |
|---|---|
| **Variance comes only from equivalent differences** | **12 of 20** (60%) |
| **Variance comes from a real spec error in at least one sample** | **8 of 20** (40%; Wilson 95% [22%, 61%]) |
| (separately) a real error shared by ALL samples, which creates no variance | 3 more groups (3, 18, 20); group 9 also has one on top of its variable error |

So "mostly real errors" does not hold for what creates the variance (the owner's condition for keeping `spec_acc` in the reward), though with n = 20 the interval is wide. But real spec errors are common in M1 in general: 11 of the 20 groups contain one somewhere (8 variable + 3 shared-only), which `spec_acc` weight 0 will not fix (see "What weight 0 gives up").

## The 20 groups

| # | task | request (short) | varies between samples | class |
|---|---|---|---|---|
| 1 | 0284be5a24 | 2x faster, strip audio, width 320 | `tolerance_s` | equivalent |
| 2 | 09e0026e55 | first 5 s, 1.5x, 1080x1920 | `audio.codec` (aac present or not) | equivalent |
| 3 | 1ada5e5192 | trim 0-2 s, square 1080, 2x faster | `tolerance_s`, `fps` (60 or absent), `rotation: 0` | equivalent (shared real error: `end_s` 2 vs the 1.0 s output) |
| 4 | 2b196cf0b7 | flip, 60 fps, first second | `container` (**matroska** in 3 of 8, mp4 expected), `audio.codec`, `tolerance_s` | **real** (wrong container) |
| 5 | 2c4bbe8fc8 | silent, first second, width 320 | `tolerance_s`, `codec`, `pix_fmt`, `1` vs `1.0` | equivalent |
| 6 | 34d9e19875 | webm for TV, 0.5x, 1080x1920 | `tolerance_s` (0.5 vs absent), `fps`, `start_s` 0 vs 0.0 | equivalent |
| 7 | 34e344a91d | trim 5 s, silent, crop 1080 square, 1.5x | `end_s` (**12.0 in 2 of 8**, gold 10.0), `tolerance_s` | **real** (wrong end time in a minority) |
| 8 | 34ed49f0f1 | mp3, +6 dB, last 2 s | `tolerance_s` | equivalent (gold's absolute LUFS is not derivable from "+6 dB") |
| 9 | 386d3a73d4 | rotate left, remove sound | `lossless` (**true** in 2 of 8, but the command re-encodes with libx264), `fps`, `pix_fmt`, `end_s` | **real** (false "lossless" claim); shared real error: width/height not swapped after the rotation |
| 10 | 4368bf81c7 | first 3 s, rotate 90, **no re-encoding** | `lossless` (omitted in all), width/height (1920x800 swapped in some samples) | **real** (the user's explicit constraint is missing; dimensions differ between samples) |
| 11 | 6a9353d7d6 | width 640, 3 s, 2x faster | `height` 267 vs 266 | equivalent (1 px rounding) |
| 12 | 6b2e4250fe | remove the first 2 s | 7 of 8 restate the input's codec, fps, 1280x720 etc. plus `end_s: 4.0`; 1 sample is exactly the gold | equivalent (over-specification; `end_s: 4.0` is questionable if `end_s` means output time) |
| 13 | 6cac188978 | trim 5 s, 1080x1920, silent | `container` (**matroska** in 5 of 8), `start_s` (**omitted**; gold 5), `end_s` | **real** (wrong container, dropped the explicit trim) |
| 14 | 79d985b8a9 | "cut out the section between 0 and 2 s", 1080x1920 | `start_s`/`end_s`: **2 of 8 read it as keep 2-4 s** (the opposite), 6 of 8 keep 0-2 | **real** (opposite readings of an ambiguous request: the user would be misled in one reading) |
| 15 | 79f43d170e | silent, width 640, drop first 1 s, 0.5x | `end_s` (**20.85 vs 18.853**: output duration wrong), `lossless` (true in 2), `audio.present` (omitted; gold False) | **real** |
| 16 | 817f192daa | webm for TV, first 5 s, "shrink to 360p" | `height` (**480** in 6 of 8, the command scales to 360), `width`, `tolerance_s` | **real** (spec contradicts the request) |
| 17 | 85ea025afa | drop 2 s, 24 fps, 360p, silent | `family` order only | equivalent |
| 18 | 86622192ff | first 2 s, 60 fps, silent, turn right | `tolerance_s` | equivalent (shared real error: width/height not swapped after "turn right") |
| 19 | 8683697e0f | join three clips to mp4 | extras (`end_s 10.0`, `tolerance_s 0.5`, `fps`, `rotation`) | equivalent (over-specification; `end_s: 10.0` unverified) |
| 20 | 980416099b | drop first 5 s, 30 fps, 480p | `tolerance_s` | equivalent (shared real error: width 854 vs 1152, an extra F3 family tag) |

## What weight 0 gives up (so the owner decides with the whole picture)

* The reward currently pays for "write the spec the way the generator does". Of the variance it creates, 60% is that (over-specification and tolerance style), which is what you wanted removed. That is the reason for weight 0.
* It also pays, weakly, for fixing real spec errors (8 of 20 groups). With weight 0 GRPO gets no gradient on them, and nothing stops them drifting. M1 already makes real spec errors in 55% (11/20) of these groups. For the product, the spec is what the user confirms, so this matters; the plan keeps `spec_acc` as an eval metric (dev, descriptive) and a drift watch is cheap: log it every step (the telemetry keeps the raw term) and compare M3 vs M1 on dev and on the test splits as a guard, not a goal.
* Separately, the shared errors (dimension swaps after rotation, `end_s` after a speed change) look like systematic gaps of the generator-to-spec mapping in M1's SFT data, not noise a reward would fix quickly.

Files: `groups-dump.md` (all 20 groups, every emitted spec vs gold), `widened/` and `t18/` (`records.jsonl` with specs, `analysis.json`), `widened-ids.txt`, `t18-ids.txt`, `sampling.log`.
