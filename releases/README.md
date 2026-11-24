# releases/

Local release packages of the model (D-053). One folder per version, `ffwd-0.6b-v<MAJOR.MINOR.PATCH>/`. Nothing here has been uploaded, renamed or published: every step below is **not run**.

## Layout of a package

`ffwd-model.json` (the manifest apps read; schema `packages/protocol/schemas/model.schema.json`, examples `packages/protocol/conformance/model-manifest.jsonl`), the two GGUFs, `adapter/` (LoRA adapter of checkpoint-60, base is the merged M1), `chat-template.jinja`, `system-v1.txt`, `README.md` (the model card, generated from `docs/hf-cards/model-card-m3.md`), `LICENSE` (Qwen3 Apache-2.0), `RELEASE_NOTES.md`, `SHA256SUMS` (every file except itself). Git ignores the GGUFs and `adapter/`; the small text files are tracked.

## Build and verify (local, safe, can be repeated)

```
uv run python -m training.export.release build --version 1.0.0 --out releases/ffwd-0.6b-v1.0.0
uv run python -m training.export.release verify --out releases/ffwd-0.6b-v1.0.0
(cd releases/ffwd-0.6b-v1.0.0 && sha256sum -c SHA256SUMS)
```

The build copies (never re-quantises) the GGUFs from `data/models/grpo-m3-ckpt60-gguf/` and refuses on any hash that differs from the evaluation manifests. It reads `../ffwd-web/app/model/canary-reference.json` and `config.js` (override the folder with `FFWD_WEB_DIR`) and refuses if they disagree. Rebuild after editing the card or `RELEASE_NOTES.md` (it rewrites `SHA256SUMS`).

## Run the CLI against the package

```
uv run python -m apps.cli.ffmpeg_agent_cli "<request>" file.mp4 --release releases/ffwd-0.6b-v1.0.0 --llama-server /path/to/llama-server [--canary]
```

The CLI (version in `apps/cli/ffmpeg_agent_cli/__init__.py`) loads `ffwd-model.json` and refuses, exit code 5 and nothing started, on a schema error, a `protocol_version` other than the one it was built for, a `min_app_version` above its own, or a shipped GGUF, system prompt or chat template whose size or sha256 differs. The GGUF is hashed once; a marker in `~/.cache/ffwd/verified.json` (keyed by path, size and mtime) skips the re-hash. It then starts llama-server with the manifest's runtime (`-c 8192 -ctk q8_0 -ctv q8_0 -fa on`, the package's template) and ends an episode whose next prompt plus 512 tokens would not fit as "too long" (exit code 6). `--model <gguf>` alone, with no manifest next to it, keeps the old defaults (`-c 4096`, f16 KV) and prints a warning.

## The two prepared steps (both dry runs unless `--go`)

```
uv run python -m training.export.push_release rename --from JustJoyful/<repo-that-moves>       # HfApi.move_repo
uv run python -m training.export.push_release upload --package releases/ffwd-0.6b-v1.0.0      # one commit, then the tag v1.0.0 on that commit
uv run python scripts/release_github.py --repo OWNER/REPO --package releases/ffwd-0.6b-v1.0.0 # gh release create (draft)
```

All three refuse when `SHA256SUMS` or `ffwd-model.json` do not verify. `upload` refuses a public repo, an existing tag, and (with `--go`) remote files outside the package unless `--delete-stale`. None of them changes visibility.

## Order of the manual steps (owner)

1. **Decide the Hub repo** (not run): no M3 model repo exists on the Hub today. `JustJoyful/ffmpeg-agent-m1-0.6b` (private) holds the M1 model; `JustJoyful/ffmpeg-agent-ckpt-grpo` holds checkpoints with optimizer states. Renaming either moves its whole history into `ffwd-0.6b`. Recommended: do not rename; let `upload` create a fresh private `JustJoyful/ffwd-0.6b`, and rename the M1 repo later if wanted.
2. `rename ... --go` (only if you chose a rename) (not run).
3. `upload --package ... ` as a dry run, read it, then `--go` (not run). The tag `v1.0.0` points at the uploaded commit; the site pins that tag or the commit hash.
4. Check the private repo contents (README renders, `sha256sum -c SHA256SUMS` on a download, no `test-real` data), then flip visibility on the Hub yourself (not run; no code for it exists).
5. Decide where the GitHub release lives (see the report), then `scripts/release_github.py --repo ... --go` creates a draft (not run); publish it by hand (not run).
