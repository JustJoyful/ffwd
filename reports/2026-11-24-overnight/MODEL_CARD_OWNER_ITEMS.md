# Model card and data card: status of the 11 owner items (updated 24 Nov 2026)

The owner decided items 1 to 11 on 2026-11-24 (recorded as D-052 in `DECISIONS.md`); the cards were edited to match. Nothing is pushed or uploaded; both cards stay for PRIVATE repos until the owner flips visibility (launch checklist in `MORNING_REPORT.md`). Only the items marked STILL OPEN need the owner.

## Model card (`docs/hf-cards/model-card-m3.md`)
1. **Repo id: DECIDED (2026-11-24).** `JustJoyful/ffwd-0.6b`. The existing private repo is renamed to it BEFORE it goes public, with redirects; the site pins the revision hash. Edited: the front matter comment and the paragraph under the title. **STILL OPEN (owner only): the rename itself** (a Hub action; nothing was renamed).
2. **Weights licence: DECIDED (2026-11-24).** Apache-2.0, the Qwen3 base licence (front matter `license: apache-2.0`, section Licence). Checked 2026-11-24 on https://huggingface.co/Qwen/Qwen3-0.6B: the page's licence field for the 0.6B model itself says `apache-2.0` (the page states nothing about the 235B or 32B models). **STILL OPEN (owner only): read the licence text on that page and quote it** (the one remaining `TODO(owner)`, in the section Licence, bullet "Base model").
3. **Repo link: DECIDED.** Text is exactly "project code: GPL-3.0, link added at release" (section How to run).
4. **Seeds: DECIDED, "single seed", no numbers.** No saved Kaggle log or output records the seed passed to the SFT or GRPO runs (the code defaults are 20261116, but the runner scripts do not log what was passed). Only the evaluation seed 20261115 (llama.cpp server and bootstrap, from `reports/2026-11-23-phase-1/manifest.json`) is quoted (Training item 3).
5. **LoRA adapter of checkpoint-60: DECIDED, include it** in the model repo next to the GGUF (section Files). Nothing uploaded yet; the upload is part of preparing the renamed repo.

## Data card (`docs/hf-cards/data-card-corpus-and-tasks.md`)
6. **What is uploaded: DECIDED (2026-11-24).** Corpus clips with their licences, the generator, ALL generated splits including test (with hashes); `test-real` stays private and is not listed, hashed or described; teacher trajectories NOT uploaded for now. Edited: front matter, intro, Exclusions, section 3. **STILL OPEN (owner only): the dataset repo id** (the card says the existing private `JustJoyful/ffmpeg-agent-corpus` until the ffwd rename; no new id was given).
7. **Dataset licence: DECIDED (2026-11-24).** Generated tasks and manifests CC BY 4.0; clips keep their own licences.
8. **DeepSeek terms review: DECIDED, recorded as done.** "§4.2(2) assigns outputs to the user; §4.2(3) permits training other models incl. distillation; snapshot sha256 `e700b82e...22de`; read by the owner 19 Nov 2026." The hash is the recorded one (`training/teacher/terms/2026-11-19/terms.json`, `training/config.py`); trajectories stay local (section 3.2).
9. **CC BY 3.0 verification dates: STILL OPEN (owner only).** Check the licence pages for Tears of Steel and for the Wikimedia Commons `Big_Buck_Bunny_4K.webm`, then write the date and URLs in section 1.2 (the paragraph starting "The manifest does not record when", the only `TODO(owner)` in the data card).
10. **`hard-v1` in MANIFEST.json: DECIDED and DONE.** The entry already existed (`extra_train.hard-v1`, sha256 `e3cb68be...` verified against the file, 300 tasks, generator 1.0); the card was wrong. Added the pool draw seed 20261120 and split-hash seed 20261116 (additive; no existing hash changed); the card table now has real numbers.
11. **Clip count: DECIDED, 35 everywhere** (22 synthetic CC0 plus 13 CC BY 3.0). The M1 hub README source (`reports/2026-11-20-m1-hub/README.md`) was fixed locally; the copy already on the Hub still says 14 real clips and changes only if that README is re-pushed (not done). Older dated reports that quote 22 or 36 were left as written.

## Before any of it goes public
See the launch checklist in `MORNING_REPORT.md` section 5: the renamed repo, the contents check of each repo (no test-real clips, no trajectories, hashes match), the licence lines, then and only then change visibility.
