# GitHub release plan: ffwd-0.6b v1.0.0 (model repo, once public)

Status: plan only. `scripts/release_github.py` was run in dry-run mode only (no `--go`); nothing was created on GitHub.

## Tag name: recommendation `model-v1.0.0`

- The repo holds code (CLI, harness, training), not only the model. A plain `v1.0.0` reads as "the software is 1.0.0"; later CLI or code releases would then collide with or confuse the model's version line (the model has its own semver in `ffwd-model.json`, D-053).
- Counter-argument: `scripts/release_github.py` hard-codes `tag = f"v{version}"` and the Hugging Face upload tags `v1.0.0` too (different repo, no clash). Using `v1.0.0` needs no change.
- Decision for the owner. If `model-v1.0.0` is chosen the script needs a one-line change (`tag = f"model-v{m['version']}"`) and the notes should say "Hub tag: v1.0.0". Either way pass the tag a target commit (see "must be true first"): the script creates a draft, and GitHub tags the default-branch tip at publish time unless `--target <sha>` is given. The script has no `--target`; add one or create the tag by hand first.

## Release notes outline (`releases/ffwd-0.6b-v1.0.0/RELEASE_NOTES.md` already exists and is the `--notes-file`)

1. One-paragraph what it is (Qwen3-0.6B + SFT + multi-turn GRPO checkpoint-60; one JSON action per turn).
2. Results with the honest framing already in the file: 95.0% (855/900) browser Q5_K_M, 96.3% (867/900) native Q8_0, paired difference -1.33 pp with CI [-2.67, -0.11] (guard not shown), generated tasks only, one seed, Q4_K_M not usable.
3. Files table with sizes and sha256, `sha256sum -c --ignore-missing SHA256SUMS` instruction (see assets note).
4. llama.cpp command, what was and was not verified.
5. Licence: weights Apache-2.0 (derivative of Qwen3-0.6B), code GPL-3.0; link to THIRD_PARTY_NOTICES.md.
6. Add before publishing: link to the Hub repo and the web app, the WebGPU-on-Intel known issue (reports/2026-11-24-canary), the private-clips caveat.

## Assets (GitHub limit: 2 GiB per asset, up to 1000 assets, no total cap)

| asset | bytes | under 2 GiB? | in the script today? |
|---|---|---|---|
| `ffwd-0.6b-v1.0.0-Q5_K_M.gguf` (shipped) | 444,411,456 | yes | yes |
| `ffwd-0.6b-v1.0.0-Q8_0.gguf` (evaluated headline) | 639,443,520 | yes | yes |
| `ffwd-model.json` | 5,311 | yes | yes |
| `SHA256SUMS` | 1,617 | yes | yes |
| `LICENSE` (Apache-2.0 Qwen3 text; the repo's own LICENSE is GPL-3.0, so consider renaming the asset `LICENSE-model-Apache-2.0.txt`) | 11,343 | yes | yes |
| `weights/model.safetensors` (merged fp16) | 1,192,134,784 (1.11 GiB) | yes | NO: the script uploads only GGUFs, manifest, SHA256SUMS, LICENSE. Add it (as e.g. `ffwd-0.6b-v1.0.0-fp16.safetensors`) only if wanted; the Hub repo already carries it. Its tokenizer.json (11 MB) and config would be needed beside it, so a zip is clearer. |
| `chat-template.jinja`, `system-v1.txt` | 793 / 4,350 | yes | NO but needed to run the model correctly (the notes say the stock template is wrong); add both. |

Gotcha: `SHA256SUMS` lists every package file (adapters, weights, README...). With only a subset of assets downloaded, `sha256sum -c SHA256SUMS` reports missing files; tell users `--ignore-missing`, or upload a SHA256SUMS regenerated for the asset subset (the manifest `ffwd-model.json` carries the per-file hashes as well).

## Exact dry-run command (run, prints only)

```
cd /home/joydeep/Projects/ffmpeg-agent
uv run python scripts/release_github.py --repo JustJoyful/ffmpeg-agent --package releases/ffwd-0.6b-v1.0.0
```

Output on 25 Nov 2026 (package verified): `DRY RUN, would run: gh release create v1.0.0 <Q5_K_M.gguf> <Q8_0.gguf> ffwd-model.json SHA256SUMS LICENSE --repo JustJoyful/ffmpeg-agent --title "ffwd-0.6b v1.0.0" --notes-file .../RELEASE_NOTES.md --draft`. The real run is the same with `--go`; it makes a DRAFT the owner publishes by hand.

## What must be true first

1. The repo is public (owner flips it) and the cleanup list is applied or consciously declined; `gitleaks` re-run on the final HEAD.
2. The tag points at a commit that is pushed to `origin/main` (not a local-only commit) and the package in `releases/` was built from that commit (`training.export.release verify` passes; `sha256sum -c` passes).
3. The Hub repo `ffwd-0.6b` at tag `v1.0.0` exists and is public (the site and the manifest URL point there; GitHub assets are for people, not for the browser).
4. DeepSeek terms review done (CLAUDE.md: nothing public until then), HF model and data cards approved, owner's review of the 50 passed outputs done.
5. `gh auth status` is logged in as the owner and the token has `repo` scope (not checked here).
6. THIRD_PARTY_NOTICES.md and the README rewrite are merged so the release page can link to them.
