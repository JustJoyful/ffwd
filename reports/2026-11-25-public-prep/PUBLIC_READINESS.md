# Public-readiness check of HEAD, 25 Nov 2026

## Model repo (`ffmpeg-agent`)

- [ ] **README is stale**: says "Phase 0 done, next Phase 1", no results, no run instructions, no limitations, "portfolio goals / resume bullets" section. Proposed rewrite: `docs/public/README.proposed.md` (not applied).
- [x] LICENSE: GPL-3.0 (`LICENSE`); `pyproject.toml` says GPL-3.0-only.
- [x] THIRD_PARTY_NOTICES.md: added (Qwen3 Apache-2.0, llama.cpp MIT, FFmpeg GPL build, ffmpeg.wasm GPL, Blender CC BY 3.0 credits, CC0 synthetic clips, DeepSeek terms, Python and npm licences). React Bits: not used (grep).
- [x] Model licence / card: `releases/.../LICENSE` Apache-2.0 + card in `docs/hf-cards/`.
- [x] No clips tracked (videos and `data/*` ignored; only manifests). `eval/test-real/` tracks only a README and a CSV header (no clips, no requests). **But** `data/corpus/manifest.json` has 3 `test-real` rows (hash and probe metadata, owner's full name in the licence string): owner decision (see CLEANUP_LIST).
- [x] No tokens/keys (gitleaks clean, see SCAN_AND_BLOBS.md).
- [ ] `/home/` paths: about 190 hits in `reports/` (96 in `reports/2026-11-23-passed-review`, 23 in `2026-11-20-main-run-smoke`, 18 in `2026-11-22-phase1-runs`, 10 in `2026-11-22-m3-ckpt60-dev`, 8 in `2026-11-22-phase1-dryrun-runs`, 7 in `2026-11-23-mlc-parity`, the rest 1 to 5 each); in docs: `DECISIONS.md:284` (1 hit); in code: `eval/run_phase0_baselines.sh` (2). README, PRD, ARCHITECTURE, EVALUATION, RULES, PHASES, CLAUDE.md: 0. The username appears in these paths.
- [ ] Leftovers: `download.txt` (2.2 MB console paste), 33 MB of llama-server logs, `CLAUDE.md` and `docs/superpowers/` (AI-assistant working files). See CLEANUP_LIST.
- [ ] Missing: CONTRIBUTING, SECURITY.md (helper security rules are in RULES.md), CODE_OF_CONDUCT, issue templates (optional). `.github/workflows/ci.yml` exists.
- [ ] Blocking by project rule (CLAUDE.md): DeepSeek terms review, HF cards approved, owner's review of 50 passed outputs.
- [ ] Release notes say a real end-to-end CLI run of the packaged model with `-ngl 99` is not verified.
- [ ] Release script uploads only some files (see GITHUB_RELEASE_PLAN.md).

## Site repo (`ffwd-web`)

- [ ] **No README tracked at all** (and `.gitignore` ignores `*.md` except `CREDITS.md`). Proposed: `docs/public/README.proposed.md`.
- [x] **LICENSE added** (GPL-3.0 text copied from the model repo; `package.json` already says GPL-3.0-only).
- [x] THIRD_PARTY_NOTICES.md added (wllama MIT, ffmpeg core GPL-2.0-or-later with source offer, React MIT, Funnel fonts OFL-1.1, posthog Apache/MIT, Meridian CC BY 4.0). React Bits: grep found nothing. `CREDITS.md` already covers media.
- [ ] Licence nuance: `sentry` (FSL-1.1-Apache-2.0) is a dev-only transitive of Lighthouse CI; not shipped.
- [x] No test-real clips or requests (`protocol/test-real-ids.json` has 3 ids only; `tests/unit/no-test-real.test.js` guards it). No tokens (one false positive, a sha256 pin). No personal paths (only synthetic `/home/me/...` strings in analytics tests).
- [ ] Launch blockers in `docs/launch-items.txt`: ffmpeg core (31 MB) exceeds Cloudflare Pages' 25 MiB limit; model manifest URL and hash not set; placeholders ([contact address], role line, SITE_URL); analytics key off.
- [ ] `.gitignore` `*.md` rule hides new docs: the new files were force-added; owner should whitelist them.
- [ ] CI exists (`ci.yml`, `protocol-drift.yml`). No SECURITY/CONTRIBUTING.

## Dependency licence lists (from the package managers)

- Python: `importlib.metadata` over the project venv (87 distributions); summary in THIRD_PARTY_NOTICES.md. One package without a licence field: `cuda-toolkit` (NVIDIA, training only).
- Site: `pnpm licenses list --prod` = 30 packages: MIT 23, OFL-1.1 2, GPL-2.0-or-later 1 (ffmpeg core), BSD-3 1, Apache-2.0 1, (Apache-2.0 AND MIT) 1, (MPL-2.0 OR Apache-2.0) 1.
