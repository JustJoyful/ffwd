# ARCHITECTURE: ffmpeg-agent

| | |
|---|---|
| **Status** | Design approved for Phase 0; items marked **[VERIFY]** must be confirmed during implementation |
| **Last updated** | 14 Nov 2026 |

---

## 1. System overview

```text
                         ┌──────────────────────── User's machine ────────────────────────┐
                         │                                                                 │
  Static site (CDN)      │   Browser tab (Chrome/Edge, WebGPU)                             │
  Cloudflare Pages ──────┼─▶ ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐  │
  (HTML/JS, COOP/COEP)   │   │ UI (React)   │◀─▶│ Agent loop (TS)  │◀─▶│ Model worker   │  │
                         │   └──────────────┘   │ spec · plan ·    │   │ WebLLM/WebGPU  │  │
  Model weights ─────────┼──────────────────────┼──────────────────┼──▶│ (MLC weights)  │  │
  Hugging Face Hub       │                      │ probe/run/check  │   └────────────────┘  │
                         │                      └───────┬──────────┘                       │
                         │                              │ structured args only              │
                         │                   ┌──────────▼──────────┐                        │
                         │                   │ FFmpeg worker       │  browser mode          │
                         │                   │ ffmpeg.wasm (MT)    │                        │
                         │                   └─────────────────────┘                        │
                         │                              │ (optional handoff, loopback only) │
                         │                   ┌──────────▼──────────┐                        │
                         │                   │ Helper app          │  power-user mode       │
                         │                   │ native FFmpeg +     │                        │
                         │                   │ llama.cpp (GGUF)    │                        │
                         │                   └─────────────────────┘                        │
                         └─────────────────────────────────────────────────────────────────┘
  PostHog (anonymous events only) ◀── counts and categories, never media, prompts or paths
```

**Offline (developer-side):** task generator → teacher/rejection-sampling data → SFT → multi-turn GRPO (Kaggle) → evaluation → export to MLC (WebLLM) and GGUF (llama.cpp) → Hugging Face Hub.

---

## 2. Components

| Component | Responsibility | Tech |
|---|---|---|
| `apps/web` | UI, capability checks, file handling, agent loop (TS), workers, analytics | TypeScript, React + Vite, WebLLM, ffmpeg.wasm |
| `apps/helper` | Local API: native FFmpeg + llama.cpp, batches, GPU encode | Python (FastAPI) controlling prebuilt `llama-server` and static FFmpeg binaries **[VERIFY packaging per OS]** |
| `packages/protocol` | **Single source of truth**: JSON Schemas for actions, spec, probe result, check result; allowlist definition; conformance test cases | JSON Schema + generated TS/Python types |
| `training/` | Task generator, media corpus, environment, teacher client, SFT, GRPO, export | Python 3.11, uv, TRL/Unsloth **[VERIFY multi-turn support]**, vLLM for rollouts |
| `eval/` | Benchmarks, baselines, statistics, reports | Python |
| `site-content/` | Per-chore landing pages | Markdown → static pages |

The **agent loop and checker exist twice** (TypeScript in the browser, Python in training/helper). Drift is prevented by the shared **conformance suite** in `packages/protocol/conformance/`: both implementations must produce identical results on every golden case (RULES §4).

---

## 3. Agent protocol

### 3.1 Loop

```text
inputs ──▶ probe(all files) ──▶ model: emit SPEC ──▶ UI confirmation ──▶ model: RUN args
                                    │                                       │
                                    ├─▶ ASK_USER(question) ──▶ user answer ─┘
                                    └─▶ UNSUPPORTED(reason, nearest_supported)
RUN ──▶ executor (allowlist-validated) ──▶ CHECK(output, confirmed spec) ──▶ pass → FINISH
                                                    │ fail / error
                                                    └──▶ observation back to model → next RUN
Turn budget: ≤ 4 RUN actions per job (configurable). Batch = same plan applied per file, checked per file.
```

The model emits **exactly one action per turn** as JSON matching `packages/protocol/action.schema.json`:

| Action | Fields | Effect |
|---|---|---|
| `spec` | `spec` object (§3.2) | Proposed output spec; shown to the user for confirmation |
| `ask_user` | `question` (one sentence) | Pauses for user input; max 1 per job in v1 |
| `unsupported` | `reason`, `nearest_supported` (optional family id) | Ends the job honestly |
| `run` | `args: string[]`, `inputs: file_id[]`, `outputs: output_id[]` | Executes one validated FFmpeg invocation |
| `finish` | `outputs: output_id[]`, `note` | Ends the job (only valid after a passing check) |

**`check` is not a model action.** The harness runs it automatically after every `run` and returns a structured observation, so the model can never skip verification.

### 3.2 Spec (output contract)

Simplified shape (the full JSON Schema lives in `packages/protocol`):

```json
{
  "family": ["F1", "F4", "F6"],
  "outputs": [{
    "id": "out1",
    "kind": "video | audio | image_sequence | gif",
    "container": "mp4",
    "per_input": true,
    "video": { "codec": "h264", "width": 1080, "height": 1920, "fps": null,
               "pix_fmt": "yuv420p", "rotation": 0 },
    "audio": { "present": true, "codec": "aac", "loudness_lufs": null, "offset_ms": null },
    "time":  { "start_s": 12.0, "end_s": 40.0, "tolerance_s": 0.1 },
    "size_max_bytes": 10485760,
    "frames": { "interval_s": null, "expected_count": null, "format": null },
    "lossless": false
  }]
}
```

Rules:
- `null` = "unconstrained". The checker only verifies fields that are set.
- **Training:** rewards use the **gold spec** from the task generator, so the model can't grade itself leniently.
- **Runtime:** checks use the **user-confirmed spec** (the model proposes; the user confirms).

### 3.3 Probe result

Normalised ffprobe-style JSON: container, duration, size, bitrate; per stream: type, codec, width/height, fps, pix_fmt, rotation (side data), sample rate, channels, start_time. The same schema is used in both runtimes.

### 3.4 Check result

```json
{ "passed": false,
  "checks": [ {"field":"video.height","expected":1920,"actual":1080,"ok":false},
              {"field":"size_max_bytes","expected":10485760,"actual":9830400,"ok":true} ],
  "measurements": { "duration_s": 28.02, "re_encoded": true, "loudness_lufs": -14.2 },
  "error": null }
```

**Measurements beyond ffprobe:**
- loudness via FFmpeg's EBU R128 meter
- frame count and interval for image sequences
- audio stream offset via **first-packet timestamps** of the audio and video streams (verifies that the *requested* offset was applied, not perceived sync). Container `start_time` is not used: MP4 edit lists hide negative offsets and ffprobe clamps them to 0 (Phase 0 follow-up T2). Offsets made with filters (e.g. `adelay`) leave timestamps unchanged and cannot be verified this way
- **implicit invariants** (checker v1.2, D-025): unless the spec changes them, output duration and audio presence equal the input's (merge: sum of the inputs), and a video/audio output has a video/audio stream. A 0.1 s clip can no longer satisfy a conversion task
- **net rotation:** `video.rotation` = clockwise degrees of the displayed picture relative to the input's, measured from picture content (one convention for spec and probe; 90 = right, 270 = left)
- **image sequences:** one frame at t = k*interval while t < duration - half a frame; explicit `expected_count` matches exactly, interval-only accepts the strict count or one fewer at the boundary (`training/config.py`)
- `re_encoded`: whether streams were copied or re-encoded
- optional quality floor (SSIM/PSNR fast; VMAF in eval only)

### 3.5 Executor & allowlist

- Input is an **argument list**. It is **never** joined into a shell string, and no shell is ever involved.
- The validator rejects anything not in the allowlist: allowed options, encoders/decoders, filters (and filter-graph syntax parsed and validated), muxers.
- Inputs and outputs are referenced by IDs. **The harness assigns the real paths.** No `-y` to arbitrary paths, no protocols (`http:`, `concat:` with external paths, `pipe:`, etc.), no `-filter_script` files from outside the job dir.
- Per-run timeout and output size cap.
- In training and the helper, each job runs in an isolated temp directory. On Linux, reuse AxiomLM-style fail-closed sandboxing (Bubblewrap + cgroups) for training rollouts.

---

## 4. Browser runtime (`apps/web`)

| Concern | Design |
|---|---|
| **LLM** | WebLLM `WebWorkerMLCEngine` in a dedicated worker; Qwen3 **non-thinking** mode; JSON-constrained output for actions **[VERIFY WebLLM structured output with the custom model]** |
| **FFmpeg** | ffmpeg.wasm **multithreaded** core in its own worker; lazy-loaded (~30 MB core) |
| **Probe** | ffmpeg.wasm `ffprobe()` if the installed version exposes it **[VERIFY]**; fallback: parse `ffmpeg -i` output |
| **Cross-origin isolation** | Multithreaded ffmpeg.wasm needs `SharedArrayBuffer` → COOP `same-origin` + COEP on the site. Use `credentialless` COEP (or self-host assets) so model files and analytics still load **[VERIFY]** |
| **Files** | `File` objects for single files; File System Access API (Chrome/Edge) for folder input/output in batches |
| **Memory** | Enforce a browser-mode input size limit (set in Phase 0). Stream/chunk where possible; free buffers after each job; never hold the model, input and output longer than needed |
| **Capability check** | `navigator.gpu` + adapter limits; estimate RAM; on failure, show system requirements + helper option |
| **Caching** | WebLLM caches weights (IndexedDB/Cache API); ffmpeg core cached by the service worker. Model version pinned in config; a version change triggers a re-download prompt |
| **Speed strategy** | For slow re-encodes: optional **dry run on a 2-second sample** to validate the command before the full run (Phase 0 decides whether it's worth it) |
| **Helper detection** | Query `navigator.permissions` for `loopback-network`; if granted or the user opts in, ping `http://127.0.0.1:<port>/health`. Chrome shows a Local Network Access prompt for public sites reaching localhost (HTTP since Chrome 142, WebSocket since 147) |

### 4.1 Model deployment to WebLLM
1. Merge LoRA into base weights (fp16).
2. `mlc_llm convert_weight` with **the same quantization as the WebLLM prebuilt build** (e.g. `q4f16_1`).
3. `mlc_llm gen_config` with the **same conversation template** as the prebuilt Qwen3 entry.
4. Upload to Hugging Face (`<user>/ffmpeg-agent-0.6b-q4f16_1-MLC`).
5. In the app config, **copy the prebuilt Qwen3 record's `model_lib`** and set `model` to our repo; override `context_window_size` if needed.
6. Only if architecture, vocab or quantization differ: compile our own WebGPU library with `mlc_llm compile --device webgpu`.

---

## 5. Helper app (`apps/helper`)

| Concern | Design |
|---|---|
| **Purpose** | Big files, batches, GPU encoding (NVENC etc.), and HEVC on machines where the browser fails |
| **Process model** | Small Python (FastAPI) service that supervises a prebuilt **llama.cpp `llama-server`** binary (GGUF model) and a **static FFmpeg** binary |
| **Binding** | `127.0.0.1` only, fixed port range |
| **Auth** | Strict `Origin` allowlist (official site only) + **pairing token**: on first connect, the helper shows a code the user types into the site; the token is stored in the site's local storage. Every request carries it |
| **API** | `GET /health`, `POST /probe`, `POST /run` (structured args), `POST /check`, `POST /agent` (full loop with local model), `GET /jobs/:id` |
| **Filesystem** | Reads/writes only inside folders the user explicitly selected in the helper; outputs never overwrite inputs |
| **Packaging** | Windows first (the biggest pain point for FFmpeg installs), then Linux, then macOS. One-file installer **[VERIFY tool: PyInstaller or similar]** |
| **Updates** | Version endpoint; the site warns if the helper is outdated (protocol version mismatch blocks use) |

---

## 6. Model

| Item | Decision |
|---|---|
| Base family | **Qwen3** (WebLLM ships prebuilt Qwen3 libraries) |
| Sizes | **0.6B** (default candidate, ~0.5 GB download at q4) and **1.7B** (~1 GB). Final default chosen from accuracy + funnel data |
| Mode | Non-thinking (short JSON actions; latency matters) |
| Context | Budget ≈ system prompt + probe JSON + up to 4 observations; target ≤ 4k tokens **[VERIFY per runtime]** |
| Browser format | MLC `q4f16_1` (or `q4f32_1` if fp16 shaders are missing on some GPUs) |
| Native format | GGUF Q4_K_M and Q8_0 (benchmark both) |
| Versioning | `agent-v{major}.{minor}-{size}`; recorded in every analytics event and evaluation report |

---

## 7. Training pipeline (`training/`)

### 7.1 Media corpus
- Short (2–20 s) clips: synthetic (FFmpeg test sources: `testsrc2`, `sine`, noise) **plus** real, licence-clean clips (own recordings, CC0 sources).
- Coverage: H.264/HEVC/VP9/ProRes-lite; MOV/MP4/MKV/WebM; with/without audio; rotation metadata; variable frame rate; 16:9 / 9:16 / 4:3; quiet audio; offset audio.
- Each clip has stored probe metadata; corpus is hash-pinned.

### 7.2 Task generator
- **Templates per chore family** (F1–F12) and **compositions** of 2–4 families.
- Every task = `(inputs, natural-language request, gold spec, difficulty, family tags, flags)`. Flags include `ambiguous` (expects `ask_user`) and `unsupported` (expects `unsupported`).
- Natural phrasing: template phrasings + LLM paraphrases (teacher budget). Paraphrases are deduplicated and checked so they keep the meaning of the gold spec.
- **Splits (hash-pinned):** train / dev / test-IID / **test-compositional** (unseen family combinations) / **test-phrasing** (held-out phrasing styles). Test splits are never used for training, tuning, few-shot examples, or teacher prompts.

### 7.3 SFT data
1. **Teacher (primary):** DeepSeek V4 Flash via API, run through the *same* agent loop and environment; **keep only trajectories that pass `check()` against the gold spec**.
   - Budget-guarded client: hard cap, off-peak bulk runs, thinking disabled, max-token caps, identical system-prompt prefix for cache hits, logging of `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`.
   - Record the model ID, date and terms-of-use snapshot in the data card.
2. **Rejection sampling (free complement / fallback):** sample the base Qwen3 model (and/or a 4-bit 8B–14B open model on Kaggle) N times per *easy* task; keep passing runs.
3. Mix, deduplicate, and cap per-family share so no family dominates.

### 7.4 Multi-turn GRPO
- **The environment executes the real tool loop during rollouts:** probe → spec → run → check → retry. Rewards see whole trajectories. *(Motivation: a NeurIPS 2026 study found single-turn RLVR gave no gain for small tool agents, while multi-turn GRPO in the live loop raised a 2B agent from 4.3% to 58.7% task completion, mostly within the first ~25 steps.)*
- **Reward (initial weights; tune on dev only):**

| Term | Weight | Definition |
|---|---|---|
| `pass` | 1.0 | Final output passes **gold** spec |
| `partial` | 0.3 | Fraction of gold-spec fields satisfied (only if not `pass`) |
| `spec_acc` | 0.2 | Field-level match of the emitted spec vs gold spec |
| `efficiency` | 0.1 | No unnecessary re-encode when a lossless/stream-copy solution exists; fewer runs |
| `clarify` | ±0.5 | Correct `ask_user` on ambiguous tasks / correct `unsupported` on unsupported tasks; penalty for unnecessary asks or refusals |
| `invalid` | −0.5 | Disallowed or unparseable action |

- **Reward-hacking guards:**
  - Size targets require duration preservation and a quality floor (SSIM/PSNR; VMAF in eval).
  - Malformed outputs are tracked separately.
  - Over-asking / over-refusing is penalised.
  - High-reward trajectories are spot-checked by hand every N steps.
  - A shuffled-reward sanity run is included.
- **Compute:** Kaggle (~30 GPU-h/week, 2×T4 preferred over P100 for vLLM compatibility **[VERIFY]**), 12 h sessions → **checkpoint every N steps + resumable data loader + deterministic seeds**. No bf16 / FlashAttention 2 on these GPUs → fp16 with care. Paid Colab L4 as fallback.

### 7.5 Export
Merged weights → (a) MLC for WebLLM (§4.1), (b) GGUF for llama.cpp. Every export is followed by a **parity eval** (same dev subset, all formats) so quantization loss is measured, not assumed.

---

## 8. Evaluation harness (`eval/`)
See **EVALUATION.md**. The harness reuses the same environment, protocol and checker as training (Python), and drives the browser build via Playwright for end-to-end and speed benchmarks.

---

## 9. Analytics (PostHog)

| Setting | Value |
|---|---|
| Identity | PostHog's anonymous distinct ID; **never call `identify`** |
| Persistence | localStorage |
| Autocapture / session replay | **Off** |
| IP capture | **Disabled** in project settings |
| Payload rules | Categories and numbers only: never prompts, file names, paths, contents |
| Ad blockers | Optional PostHog reverse proxy on our domain to reduce undercounting |

**Events and properties:**

| Event | Properties |
|---|---|
| `site_visit` | `landing_page` (chore slug or home), `referrer_domain` |
| `capability_checked` | `webgpu` (bool), `fail_reason` (category) |
| `model_load_started` / `model_load_completed` | `model_version`, `cache_hit`, `ms` |
| `edit_started` | `families[]`, `mode` (browser/helper), `input_size_bucket`, `n_files_bucket` |
| `spec_confirmed` | `edited_by_user` (bool) |
| `edit_completed` | `passed_check`, `runs`, `seconds_bucket`, `re_encoded`, `model_version` |
| `edit_failed` | `reason_category` |
| `ask_user_shown` / `unsupported_shown` | `category` |
| `helper_detected` / `helper_handoff` | `mode` |

Dashboards: activated users, 30/60-day returning %, monthly actives, funnel, success by family, unsupported categories, model-load drop-off by model version.

---

## 10. Hosting & deployment

- **Static site:** Cloudflare Pages (custom headers via `_headers` for COOP/COEP). Not GitHub Pages: it can't set these headers.
- **HTTPS required** (WebGPU secure-context features; Local Network Access only from secure origins).
- **Model weights:** Hugging Face Hub (versioned repos).
- **Helper releases:** GitHub Releases with checksums.
- **CI (GitHub Actions):** lint, unit tests, conformance suite (TS + Python), small golden eval on CPU, Playwright smoke test, build.

## 11. Repository layout

```text
ffmpeg-agent/
├── apps/
│   ├── web/                 # React + Vite site, workers, agent loop (TS)
│   └── helper/              # FastAPI helper, binaries manager, installer config
├── packages/
│   └── protocol/            # JSON Schemas, allowlist, generated types, conformance cases
├── training/
│   ├── corpus/              # media corpus manifests (+ hashes), not raw media in git
│   ├── taskgen/             # templates, compositions, paraphrase, splits
│   ├── env/                 # Python agent loop, executor, checker, sandbox
│   ├── teacher/             # budget-guarded API client, generation scripts
│   ├── sft/  grpo/          # training configs and scripts (Kaggle notebooks generated from these)
│   └── export/              # MLC + GGUF export and parity eval
├── eval/                    # baselines, runners, statistics, report templates
├── site-content/            # per-chore landing pages
├── docs/                    # these documents
└── reports/                 # immutable evaluation outputs (git-tracked summaries only)
```

## 12. Configuration & versioning
- One config module per package (`config.ts`, `training/config.py`, `helper/config.py`). No scattered constants.
- Protocol version (`protocol_version`) shared by web, helper and training; mismatches fail loudly.
- Model version in config and in every analytics event and report.

## 13. Security & privacy model (summary)
- No shell anywhere; allowlisted structured FFmpeg arguments only.
- Browser mode: media stays inside the tab's memory; nothing is uploaded.
- Helper: loopback-only, Origin + pairing token, user-approved folders only, protocol-version checks.
- Analytics: anonymous, no IP, no content; privacy page in plain language.
- Supply chain: pinned lockfiles; helper binaries downloaded only from pinned URLs with checksums.

## 14. References (checked Nov 2026)
- ELLMPEG (2026): https://arxiv.org/html/2602.00028v1, dataset https://github.com/zoha-az/ELLMPEG
- Multi-turn RLVR for small tool agents (NeurIPS 2026): https://neurips.cc/virtual/2026/171163
- CacheRL (2026): https://arxiv.org/html/2606.14179
- Chrome Local Network Access: https://developer.chrome.com/docs/modern-web-guidance/guides/security/local-network-access
- PostHog data-collection controls: https://posthog.com/docs/privacy/data-collection
