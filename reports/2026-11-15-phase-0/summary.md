# Phase 0 summary: go/no-go spike

**Verdict: GO** (preregistered rule, eval/PREREGISTRATION.md). Two items remain with the owner, listed under Open items.

## 1. Is there a gap worth training for? (EVALUATION Q1)
50 spike tasks (dev split), same harness and checker for every system. Full table: `baselines.md`; caveats: `baselines-notes.md`.

| System | Success | 95% CI |
|---|---|---|
| Base Qwen3-0.6B (B1 = B2) | 0% | 0-0% |
| Base Qwen3-1.7B (B1 = B2) | 8% | 2-16% |
| DeepSeek V4 Flash + loop (X1) | 94% | 86-100% |

Paired gap X1 - best base (1.7B): **+86 pts [+76, +94]**. GO needs >= 25; RETHINK (base >= 85%) not triggered.
Caveats: base models fail mainly by copying the prompt's example actions (0.6B emits unparseable JSON; 1.7B refuses); one X1
failure is probably a checker-v0 false negative (A/V offset), not re-graded; GGUF Q8_0 not fp16; 50 hand-drafted tasks, owner review pending.
DeepSeek spend for everything in Phase 0: **$0.0282 of $4.00**.

## 2. Browser feasibility (live site https://ffmpeg-agent-spike.pages.dev; owner desktop, RTX 3050 6 GB, headed Chromium 159)
| Check | Result |
|---|---|
| COOP/COEP on Cloudflare Pages | present on pages and assets; page cross-origin isolated |
| ffmpeg.wasm multithreaded (core-mt 0.12.10, FFmpeg 5.1.4) | loads in ~1.4 s; **needs `-threads 4` on every output or re-encodes deadlock** |
| **HEVC decode in ffmpeg.wasm** | **works** (4 s 1080p HEVC to H.264 in 0.9 s) so F3 can stay in browser mode |
| ffprobe in ffmpeg.wasm | present but ends in `Aborted()`; run last or reload the core |
| Chores, browser vs native | F1 0.13 s vs 0.05 s; F4 5.2 s vs 0.68 s (~7.6x); F7 0.23 s vs 0.17 s |
| WebGPU adapter | `high-performance` resolves to NVIDIA (Ampere); `low-power` resolves to the Intel iGPU, so the page now refuses to load a model unless the discrete GPU is selected |
| WebLLM Qwen3-0.6B q4f16_1 (prebuilt) | download 353 MB; cold load 43-48 s; decode ~80 tok/s, prefill ~570 tok/s; non-thinking mode verified (empty `<think>` block) |
| In-browser loop F1/F4/F7 end to end | **scripted proof passes for all three** (parse -> validate -> ffmpeg.wasm -> check, on the live site). The real 0.6B model never reaches ffmpeg (0/3), including with JSON-constrained output, matching the native 0% baseline |
Files: `browser-pages-ffmpeg.json`, `browser/phase0-browser-owner-desktop-0_6b-json{0,1}.json`, `native-timing.json`.

## 3. Kaggle / training compute (D-018: TRL rollout_func)
Toy multi-turn GRPO on one T4 (fp16): **256 s/step, 0.071 GPU-h/step** for 16 rollouts (HF generate, upper bound). 6 of 10 steps ran.
Resume verified on the owner's RTX 3050 only: the Kaggle session idled out and /kaggle/working was wiped. Details: `grpo-toy/`.

## 4. Decisions for DECISIONS.md (D-019 CDN core, D-020 below)
- Browser-mode input size limit: **not measured** (100/500 MB memory test not run); Phase 2 task. Until then large files go to the helper.
- HEVC path: browser-capable. System requirements: desktop Chromium with WebGPU and a discrete GPU recommended; hybrid laptops must select the NVIDIA adapter.
- Default model: 0.6B is the candidate (353 MB). 1.7B was not loaded in the browser.
- Compute plan: at <= 0.071 GPU-h/step a 200-step GRPO run is <= 14 GPU-h (half a weekly quota); vLLM should cut it. Checkpoints must be pushed off Kaggle every save.

## Open items for the owner
1. Review the 50 tasks (`data/tasks/dev/spike-v0.jsonl`); edits would create `spike-v1`, reported separately.
2. Run the browser spike on 1-2 other machines; the peak-memory test (100/500 MB inputs) and 1.7B browser load are still unmeasured.

## Incidents worth remembering
Two desktop crashes came from RAM, not the GPU: llama-server's default 8 GB prompt cache (`--cache-ram 0` now set) and ~7 GB of scratch files in the RAM-backed /tmp (freed). Heavy runs now go in capped systemd units.
