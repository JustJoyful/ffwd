# Cleanup list (NOT committed; owner approves first). Nothing below has been changed.

History stays as is (owner decision), so everything removed here remains reachable in old commits; this only changes HEAD. All 22 commit hashes cited in DECISIONS/PHASES/EVALUATION/reports are ancestors of HEAD (checked), so none of this breaks them.

## Model repo (`ffmpeg-agent`)

| Path / pattern | Size | Why | Cited by | Recommendation |
|---|---|---|---|---|
| `training/teacher/terms/2026-11-19/*.html` (2 files) and `*.headers.txt` (2 files) | 36 K + 40 K + 2 x 4 K | Raw copies of DeepSeek's published terms; republishing a third party's page is avoidable | `reports/2026-11-19-teacher-bulk/DATA_CARD.json`, `reports/2026-11-19-teacher-pilot/DATA_CARD.json` (file names), `training/config.py` and `training/teacher/fetch_terms.py` (file names; check whether a test re-verifies the files before removing) | `git rm` the 4 files, KEEP `terms.json` (URL, fetch time, per-page sha256, snapshot sha256). Add a note in `terms.json` or a README beside it: "raw snapshot archived privately by the owner". The data-card quote of section 4.2 is in the data card, not in `terms.json` (which has only the owner's one-line confirmation). |
| `download.txt` (repo root) | 2.2 MB | A pasted Kaggle/Jupyter console log ("Debugger warning: frozen modules...") committed by accident in a GRPO fix commit | no citation found (grep) | `git rm` |
| llama-server logs `reports/**/server*.log`, `*.log.gz`, `llama-server.log`: 26 files | 33 MB total (7.3 MB `2026-11-22-phase1-runs/server-B2.log`, 7.1 MB `2026-11-20-t18-pass-rates/server.log`, 5.2 MB `2026-11-20-grpo-pool/server.log.gz`, 2.5 MB x2 `phase1-runs/server-M1.log`, `server-M3.log`, 2.3 MB `t18-pass-rates/server-unseen.log`, ...) | Noise: raw llama.cpp stderr; contain absolute paths (`/home/...`) | `server.log` is named in 3 files, `sampling.log` in 3, `build.log`, `prepare.log`, `kaggle-session*-error.log` in 1 each (report text/manifests that list artefacts); `reports/2026-11-24-canary/llama-server.log` is referenced by the canary summary | Remove the large server logs (the 10 over 0.7 MB, about 31 MB) and add the pattern to `.gitignore`. Keep small build/error logs (cited, few KB). If a manifest lists a log by hash, note "removed from HEAD, in history at <commit>". |
| `reports/2026-11-20-kaggle-smoke/evidence-pasted-by-owner.txt` | small | Owner pasted text; check it contains no account details before going public | cited in that report | Owner reads it, then keep or remove |
| `data/corpus/manifest.json`: 3 rows with `role: test-real` (`hevc_phone`, `screen_rec`, `wa_compressed`), licence string "own recording (owner <full name>)" | few KB | Metadata only (hash, probe) of the owner's private test clips, plus the owner's full name in the licence field. The data card says these rows are private and excluded from the Hub copy | the corpus hash pinned in task/test records covers this file, so editing it changes the pinned corpus hash | Owner decision. Do NOT edit silently: either accept (the rows are in history anyway) or publish a filtered manifest with a new documented hash. Also `eval/test-real/README.md` and `requests-template.csv` are tracked (instructions and a CSV header only, no clips, no requests: OK). |
| `reports/2026-11-23-passed-review/review-sheet.md` etc. with `/home/joydeep/...` paths (about 190 hits in reports/, 96 in that one folder) | small | Reveals the OS username and directory layout | many | Low value to scrub; leave unless the owner minds. DECISIONS.md line 284 and `eval/run_phase0_baselines.sh` (2 lines) are the only hits in docs/code that matter. |
| `CLAUDE.md` (root) | 9.5 KB | Operating instructions for an AI assistant, mentions "the owner is a 2nd-year CSE student ... portfolio project" | README doc map lists it | Owner decision: keep (it is a legitimate dev doc) or move to `docs/`. README.md also says "a small language-model agent that I train myself" and "Portfolio goals / resume bullets": consider trimming for a public README (see `docs/public/README.proposed.md`). |
| `docs/superpowers/plans/*.md` (2), `.superpowers/` (ignored already) | small | Internal planning files | CLAUDE.md, PHASES | Keep (history of decisions) or remove; low risk |
| Local `.git`: 23 unreachable pre-rewrite commits, a 444 MB Chromium profile blob and 377 profile objects held only by the reflog (see SCAN_AND_BLOBS.md) | 860 MB loose | Not reachable from any branch or tag, so a push does not send them | none | Local only, after the owner agrees: `git reflog expire --expire=now --all && git gc --prune=now` (frees about 850 MB; discards the pre-rewrite hashes, none of which are cited). |

Proposed `.gitignore` additions (model repo): `*.log`, `*.log.gz`, `download.txt`, `reports/**/server*.log*`, `*.har`, `.claude/`, `graphify-out/`, `scratch-prep/`. (`reports/**/.profile/` is already ignored.) Do not add `*.md`.

## Site repo (`ffwd-web`)

Tracked: 1 365 loose objects, 9.7 MB `.git`, largest blob 0.77 MB. No logs, no `.profile`, no mockups (ignored), no `.claude/` (ignored).

| Path | Size | Why | Recommendation |
|---|---|---|---|
| `docs/launch-items.txt` | 4 KB | Internal launch to-do with placeholders ("[contact address]", R2 plan) | Keep or move to an issue; harmless. |
| `public/media/mer-loop.mp4` + 9 jpgs | 0.9 MB | Meridian clips, CC BY 4.0, credited on the page and in `CREDITS.md` | Keep (attribution present). |
| `protocol/test-real-ids.json` | 60 B | Names of 3 private test-real clip ids (no content) | Keep; ids only. |
| `tests/unit/analytics.test.js` has `/home/me/holiday.mp4` | | Synthetic privacy-test string, not a real path | Keep. |
| `.gitignore` has `*.md` (only `CREDITS.md` allowed) | | New public files `README.md`, `LICENSE` (not .md), `THIRD_PARTY_NOTICES.md` would be ignored; the ones added here were force-added | Owner decision: change the rule to allow `README.md` and `THIRD_PARTY_NOTICES.md` (I did not edit the tracked file). |
| `pnpm-lock.yaml` | 0.2 MB | Normal | Keep |

Proposed `.gitignore` additions (site): `!README.md`, `!THIRD_PARTY_NOTICES.md`, `!docs/public/*.md`, `*.log`, `.lighthouseci/` (present).
