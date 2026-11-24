# Secret scan and large-blob audit, 25 Nov 2026

Tool: gitleaks 8.30.1 (already installed at `~/.local/bin/gitleaks`; not downloaded), default rules, `gitleaks git --log-opts="--all" --redact`. Raw JSON reports were not kept (14 MB, they contain only redacted matches); `gitleaks-triage.toml` in this folder is the config used for the second pass.

## Result: no real secret found in either repo

| | commits scanned (all refs) | raw findings | after triage |
|---|---|---|---|
| ffmpeg-agent (model) | 232 | 12,303 (all `generic-api-key`) | 0 real |
| ffwd-web (site) | 100 | 1 (`generic-api-key`) | 0 real |
| HEAD working tree (`git archive HEAD` + `gitleaks dir`), model | | 2 | 0 real (same false-positive class) |
| HEAD working tree, site | | 1 | 0 real |

Triage evidence:
- Model repo: 12,303 of 12,303 matches are the JSON field `"content_key": "<64 hex chars>"` in task files (`data/tasks/**/v1.jsonl`, `reports/**/tasks*.jsonl`, `sample-tasks.jsonl`, `records.jsonl`). It is the sha256 of the task content (the hash-pinned split id; the task id is its first 10 characters, e.g. `dv-00607d212c-...`). Entropy 3.6 to 4.0, 64 hex chars exactly. With an allowlist for that exact pattern (`gitleaks-triage.toml`) the history scan reports "no leaks found".
- Site repo: 1 match, `protocol/PIN.json` line 7 (commit `0168330`): `"conformance/chat-template-tokens.json": "<sha256>"`, a file-hash pin in a JSON map (the line is a path-to-sha256 entry, like its neighbours).
- Independent regex sweep across every commit of both repos (`git grep` for `hf_...`, `ghp_/gho_/ghu_/ghs_/ghr_...`, `github_pat_...`, `sk-...`, `AKIA...`, PEM private key headers, excluding jsonl): 0 hits. A broader `api_key`-style grep of HEAD hits only `tests/test_policies.py:93` (`DEEPSEEK_API_KEY=from-dotenv`, a test fixture) and code/tests that mention the words. `.env*` is git-ignored in both repos and no `.env`, `*.pem`, `*.key` or credential file is tracked. `tests/test_no_secrets.py` exists in the model repo.
- Note: all 238 commits of the model repo carry the author e-mail of the owner's personal Gmail address (git metadata); unavoidable with full history, mentioned so it is a conscious choice.

## Largest blobs reachable from refs (top 10 each; `git rev-list --objects --all`)

Model repo:
| MB | path |
|---|---|
| 7.24 | reports/2026-11-22-phase1-runs/server-B2.log |
| 7.02 | reports/2026-11-20-t18-pass-rates/server.log |
| 6.08 | reports/2026-11-22-phase1-runs/runs/B2-test-iid/episodes.jsonl |
| 5.15 | reports/2026-11-20-grpo-pool/server.log.gz |
| 4.70 | reports/2026-11-20-grpo-pool/sample/records.jsonl |
| 3.97 | reports/2026-11-16-phase1-dev-baselines/B2-qwen3-0.6b-dev-v1/episodes.jsonl |
| 3.70 / 3.51 / 3.50 | data/tasks/train/v1.jsonl (three versions) |
| 2.54 | reports/2026-11-22-phase1-runs/runs/B2-test-phrasing/episodes.jsonl |

Site repo:
| MB | path |
|---|---|
| 0.54 | public/media/mer-loop.mp4 |
| 0.26 | protocol/conformance/chat-template-tokens.json |
| 0.19 x4, 0.12, 0.11 x3 | pnpm-lock.yaml (several versions) |
| 0.05 | public/media/mer-poster.jpg |

No blob over 8 MB is reachable in either repo; no `.gguf`, `.safetensors` or `.mp4` over 50 MB, no `.gguf`/`.safetensors` at all, in any ref.

## The 424 MB Chromium profile

- **Site repo: confirmed it never reached any commit.** Checked all refs plus the reflog (`rev-list --objects --all --reflog`), plus every object in the store (`cat-file --batch-all-objects`, 1,365 objects, largest 0.77 MB, none over 50 MB), no path containing `.profile` or `chromium`. `.git` is 9.7 MB. Branches: `main`, `stream-P` (a worktree `ffwd-web-P` exists); the 100 commits scanned cover both.
- **Model repo: the profile WAS committed once, then removed by a `git filter-branch` rewrite** (reflog entry `HEAD@{6} filter-branch: rewrite`, at `375e23d`). The path was `reports/2026-11-24-overnight/app-smoke/.profile/` (377 objects; the 444,411,456-byte file is blob `6e6c993e...`, a profile `File System` entry, plus a 32.7 MB cache blob). Today **no ref (branches, `origin/*`, tag `b0-frozen-paraphrase`) reaches those objects**; they exist only in the local object store and reflog (23 unreachable pre-rewrite commits). A push or GitHub clone does not carry them. `.gitignore` now has `reports/**/.profile/`. Caveat for the owner: that rewrite changed hashes of the commits after the first modified one (the tail of 24 Nov); all hashes cited in the docs are still ancestors of HEAD (checked: 22 commit ids). If anything was pushed to `origin` before the rewrite, GitHub may still hold the old objects: `origin/main` currently contains none of them (fetch state at scan time); I did not touch the network.
- Local clean-up option (needs the owner's approval, not run): `git reflog expire --expire=now --all && git gc --prune=now`; frees about 850 MB of `.git`.
