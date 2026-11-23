# GGUF in the browser: spike report (23 Nov 2026)

Criteria were fixed before any measurement (`CRITERIA.md`, 20:55 IST; the commit precedes every run). Dev only, no test split, no paid call. One machine (the owner's laptop), one seed, greedy decoding, the same 100 dev tasks as the MLC and GGUF parity runs. Numbers come from `results.jsonl`, `*.parity.json`, `*-bridge/turns.jsonl` and the JSON files in each folder here; `manifest.json` has commits, hashes, versions, flags and hardware.

## Verdict (candidate: M3 Q5_K_M, wllama 4.0.0, Chromium 159)

| # | Criterion | WebGPU path (the product path) | CPU/WASM path (no usable GPU) |
|---|---|---|---|
| C1 | dev parity >= 95/100 | **PASS 96/100** (97 with q8_0 KV) | **PASS 95/100** (exactly at the bar) |
| C2 | median turn <= 5 s | **PASS 2.16 s** (p90 3.8 s, max 15.6 s) | **FAIL 6.83 s** (p90 11.6 s, max 63.7 s; first turn 10.3 s) |
| C3 | download <= ~500 MB | **PASS 455.2 MB** (model 444.4 + wasm 10.8; wasm is about 2.1 MB brotli) | same |
| C4 | load times (reported) | cold 1.8 s from localhost, warm 1.0 s; **cold from Hugging Face 49 s** | cold 1.4 s, warm 0.7 s |
| C5 | tab responsive during an F4 re-encode | **PASS**: longest main-thread stall 2.6 ms (limit 200) | **PASS**: 4.0 ms |
| C6 | real accelerated paths asserted | **PASS** (below) | **PASS** (below) |

So the WebGPU path meets all six; the CPU path meets all but C2. The CPU path is not a quantisation problem, so the QAT plan is **not** triggered by this result (the plan is only written if the product path fails). It is a product decision what a no-GPU visitor gets (the helper app, or a slow-but-working browser mode with a stated wait). Q4_K_M fails C1 (62/100 in the browser), Q6_K fails C3 once the runtime is added (495.1 + 10.8 = 505.9 MB), Q5_K_M is the one that passes everything.

## 1. Runtime choice

**wllama 4.0.0** (llama.cpp compiled to WebAssembly, with a WebGPU backend). Facts checked at the sources (GitHub API, release notes and README of 22–23 Nov 2026, `npm view`, and by running it):
- **Licence MIT** (llama.cpp MIT too). Maintained: 4.0.0 published 22 Nov 2026, commits on 23 Nov, 1.4k stars. **The 4.0.0 release is one day old** (the previous, 3.13.0, is from 8 Nov and is about 2x slower on CPU by the maintainer's numbers). It is exact-pinned. Note: `pnpm add` added a `minimumReleaseAgeExclude` entry for it on its own, i.e. pnpm's release-age cooldown would have refused a package this new.
- **WebGPU or CPU?** Both. CPU/WASM-SIMD always; WebGPU backend offloads layers (here 29 of 29). `isSupportWebGPU()` only tests `navigator.gpu`, so the adapter assertion in the spike is our own.
- **Multithreaded under COOP/COEP?** Yes; it needs cross-origin isolation for threads (the page was served with the site's exact headers: COOP same-origin, COEP credentialless); 6 threads were used here. Single-thread otherwise.
- Raw plain-text completion (`createCompletion({prompt})`), `tokenize()`, `cache_type_k/v`, `flash_attn`, `n_ctx`, split GGUF and parallel ranged download are all exposed. The runtime's llama.cpp is `b12637`, **ours was `b12032`**: different builds, so outputs are not bit-identical (see parity).
- Why this one: it is the llama.cpp runtime in browser form, so the browser, the helper (`llama-server`) and the CLI can all use **one GGUF artifact** with one set of parity numbers; MLC/WebLLM was rejected on the evidence (D-049); transformers.js would need a different artifact (ONNX) and a new conversion and parity cycle. Not verified: Firefox, Safari, Edge, Apple/Intel/AMD GPUs; Chromium here is Playwright's build, not retail Chrome.

## 2. Prompt rendering and tokenizer (done in the ffwd-web repo, committed)
`app/agent/chat-template.js` is the JS port of `training/env/chat_template.py`. The runtime only ever gets plain text. Checks: (a) Vitest `tests/unit/chat-template.test.js`: byte-identical to all 3 golden renders of `chat-template.json` and to 11 real agent prompts (`chat-template-tokens.json`, new, 14 cases, in `packages/protocol/conformance`); (b) the stored token ids come from native llama.cpp `/tokenize`, and the Python test also shows the HF tokenizer gives the same ids; (c) `tests/browser-gguf/tokenizer.test.js` (opt-in, `FFWD_GGUF=... pnpm test:browser-gguf`) loads the GGUF in real Chromium and checks that wllama's own `tokenize()` gives those ids **and** that its completion path counts the same prompt length, on the CPU and the WebGPU leg: 14/14 on both.

## 3. Dev parity (same 100 tasks, same harness, checker and run budget)

| model, runtime | success | native llama.cpp, same quant | native Q8_0 (97) | median turn | gen tok/s | prompt tok/s | first turn identical to native same quant |
|---|---|---|---|---|---|---|---|
| Q4_K_M, WebGPU | 62 | 60 | -35 pp [-45, -26], p < 1e-9 | 2.32 s | 55.1 | 184.7 | 85% |
| **Q5_K_M, WebGPU** | **96** | 97 (-1 pp, p = 1.0) | -1 pp [-5, +2], p = 1.0 | 2.16 s | 55.4 | 199.0 | 91% |
| Q5_K_M, WebGPU, KV q8_0 | 97 | 97 | 0 pp [-3, +3] | 2.29 s | 52.9 | 190.2 | 83% |
| Q6_K, WebGPU | 98 | 99 | +1 pp [0, +3] | 2.10 s | 54.7 | 207.9 | 93% |
| Q5_K_M, CPU | 95 | 97 | -2 pp [-5, 0], p = 0.5 | 6.83 s | 17.4 | 55.4 | 74% |

The browser reproduces the native result for each quant within one or two tasks (McNemar p >= 0.5), and Q4_K_M collapses exactly as it did natively, so the cliff is the model's, not the runtime's. Invalid-action episodes: 0 for Q5_K_M, Q6_K and the KV q8_0 run; 12 for Q4_K_M. Transcripts are not bit-identical to native (different llama.cpp build, different kernels): 62% of Q5_K_M transcripts are identical, 91% of first turns. Prompt tok/s is processed tokens over processing time with prefix reuse on, so it blends cold first turns with small follow-ups; first turns alone take a median 3.5 s wall.

## 4. Why the 15.6 s turn
It is turn 5 of `dv-f383406e52-sympt`, a late turn of a retry episode (the model re-ran a failing command 4 times, each with a 270-token reply). Prompt 5,129 tokens, **4,300 of them cached (warm)**; 829 new tokens (the previous reply plus a long ffmpeg error observation) took 8.5 s to process (98 tok/s, slow at long context) and the 274-token reply 7.1 s (39 tok/s, also slower at long context). It is not a cold start. The three slowest turns of the whole run (15.6, 13.3, 11.4 s) are turns 5, 4 and 3 of this one episode (the same two-input `filter_complex` command failing four times until the run budget ended), each longer than the last because the prompt grows. The p90 over all 307 turns is 3.8 s.

## 5. Context length and KV cache
**Prompt length on all 300 dev episodes** (M3 Q8_0 run, every turn re-tokenized; need = the longest prompt plus its reply): median 1,795, p90 2,059, p99 4,573, **max 4,659**. Over 4,096: **3 of 300** (1%); over 6,144: **0**. First prompt 1,343 to 1,852 tokens. The harness limits (8 turns, 512 tokens per reply, observations up to 928 tokens seen) allow 13.5k tokens analytically, but nothing near it occurred.
**Proposal: `n_ctx` 8192**, KV cache q8_0. No history truncation (the format stays as trained). If the next prompt plus the 512-token reply budget would not fit, the loop ends the episode with a plain "this job got too long" message and counts it as not done, the same as running out of turns; wllama otherwise fails with a `kv_cache_full` error. 6,144 would cover every dev episode too, but gives little margin; 4,096 would break 1%.
**KV cache type** (`cache_type_k/v` are exposed and work on both paths; q8_0 V needs `flash_attn`):

| | KV buffer | GPU memory in use after load (device, includes 14 MiB of other use) | CPU path resident memory after load |
|---|---|---|---|
| f16 (default) | 896 MiB | 1,416 MiB | 2,649 MiB |
| q8_0 K and V, flash attention on | 476 MiB | 1,000 MiB (peak 1,078 during the 100-task run) | 2,225 MiB |
| q8_0 K only | 686 MiB | 1,206 MiB | n/a |

q8_0 K+V saves 420 MiB (30% of the GPU footprint), parity 97/100 (f16: 96), median turn 2.29 s against 2.16 s, generation 4% slower. n = 100 cannot rank 96 against 97; it shows no loss. llama.cpp warns that flash attention over K/V rows runs on the CPU on this backend (missing GPU support); the speed here did not suffer, other hardware is untested. Weights are 418 MiB on the GPU. Resident-memory sums over the browser's process tree double-count shared pages, so only the GPU numbers and the before/after differences are used.

## 6. Hosting (verified, with one stand-in)
- **Hugging Face Hub, public model repo** (checked on a public file): the preflight on `huggingface.co` reflects the origin and allows `range`; the 302 goes to `us.aws.cdn.hf.co` which answers `206` with `Access-Control-Allow-Origin: *` and `Accept-Ranges: bytes`. In real Chromium under **COEP credentialless**, a cross-origin ranged `fetch` returned 206 type `cors`, and wllama downloaded and loaded the file. COEP credentialless needs no CORP header for a CORS fetch.
- **Real cold download** from that CDN of a **stand-in** (`unsloth/Qwen3-0.6B-GGUF` Q5_K_M, 444,415,680 bytes against our 444,411,456): **49 s (8.9 MB/s, 71 Mbit/s)** for 1, 4 and 8 connections alike (49.7, 50.6, 48.7 s). Link check: one ranged curl got 9.4 MB/s and four in parallel about 11 MB/s in total, so **this machine's link is the limit**, not the connection count. At other speeds (arithmetic, not measured): 25 Mbit/s about 2.4 min, 100 Mbit/s about 36 s, 300 Mbit/s about 12 s, plus the 2 MB wasm. I could not measure our own file: our repos are private, and uploading it publicly is blocked until the DeepSeek terms review.
- **Split GGUF and parallel download:** wllama 4 loads a single file as-is and downloads files over 64 MB in parts over several connections (default 4; observed peak of 4 requests in flight locally). A split model (6 shards made with `llama-gguf-split --split-max-size 100M`, loaded from the first shard's URL) also works: 14/14 token ids match. Splitting is only needed where a host caps file size (Cloudflare Pages: 25 MiB per file; R2 has no such cap).
- **R2:** no Cloudflare tooling or credentials here, so not tested. Needs CORS with `Access-Control-Allow-Origin` for the site and `Range` allowed, and `Accept-Ranges`.
- **Recommendation:** **Hugging Face Hub (public model repo) as the primary host** for the one GGUF: free CDN, CORS and ranges verified, versioned by commit hash, and the helper and CLI download the same file from the same URL. Pin the revision hash in the app config and verify the sha256 after download. Keep **R2 on `assets.ffwd.app` as the fallback** (already planned for the FFmpeg core), switched by one config value, so the app does not depend on one third party. The repo must be public to be usable from a browser (a private one needs a token), so this waits for the DeepSeek terms review. Not measured: HF rate limits and availability under real traffic.

## 7. Quant choice
Smallest quant that is not worse than Q8_0 on dev: **Q5_K_M**. Q4_K_M is clearly worse (62 against 97, native 60). Q5_K_M is level with Q8_0 (browser 96 or 97; native 97 each; 444.4 MB against 639.4 MB). Limit: 100 tasks cannot prove "within 2 pp" (the paired interval is [-5, +2]); they show no measurable loss and a cliff one step below. The 900-task test row (`TEST_RUN_PLAN.md`) is what can tighten it. Not tried: Q4_K_S, Q5_K_S, IQ-quants, an importance matrix. Because the same GGUF serves the browser, the helper and the CLI, Q5_K_M as the single artifact also removes Q8_0 from the shipping set; that is the owner's decision (native Q5_K_M scored 97/100 on the same sample).

## 8. Coexistence (Q5_K_M, one F4 re-encode `f4Scale480` of the 100 MB, 60 s 1080p clip in ffmpeg.wasm core-mt 0.12.10, the site's own `FfmpegSession`, while the model generates)

| | ffmpeg alone | ffmpeg with model | slowdown | model gen tok/s alone | with ffmpeg | slowdown | model prompt tok/s alone / with | longest main-thread stall |
|---|---|---|---|---|---|---|---|---|
| WebGPU | 20.6 s | 21.6 s | 1.05x | 58.9 | 60.6 | none | 272.7 / 235.4 (1.16x) | 2.6 ms (idle 0.3) |
| CPU | 20.9 s | 29.3 s | 1.40x | 20.6 | 18.1 | 1.14x | 76.8 / 64.9 (1.18x) | 4.0 ms |

7 of 8 completions overlapped on WebGPU, only 2 of 3 on the CPU path (thin). With the model on the GPU the two do not compete much; with the model on the CPU they share the cores and ffmpeg pays most. The exit log ends in `Aborted()` with code 0 and a correct 21.5 MB output (ffmpeg.wasm's normal exit).

## 9. Environment and assertions (C6)
Laptop: Intel i5-12450HX (12 threads), 16 GB RAM, NVIDIA RTX 3050 6 GB Laptop, Linux. Chromium 159.0.8154.6 (Playwright 1.65.1, new headless), flags for the GPU path `--enable-unsafe-webgpu --enable-features=Vulkan --use-angle=vulkan` (without `--use-angle=vulkan` headless gets a software adapter), none for the CPU path. Every run asserts before it counts: cross-origin isolated, SharedArrayBuffer, multithreaded (6 threads); on the GPU path additionally an adapter that is not a fallback and not swiftshader/llvmpipe (here `nvidia`/`ampere`, `shader-f16` present, 29 of 29 layers offloaded, a WebGPU line in the runtime log); a run that fails an assertion is discarded. Memory note: `systemd-run -p MemoryMax` did not contain Chromium (cgroup peak about 290 MiB against 2.6 GB resident), so that cap protected nothing here and the earlier CPU run was not throttled by it; the sampler added for the later runs reads GPU use from `nvidia-smi`.

## 10. Limits, and what was not done
One machine and one browser build; one seed; n = 100 (an interval of about +-5 pp); the dev sample is the same one used to choose the settings. The native references are llama.cpp b12032, the browser runtime b12637. The Q5 GPU run predates the memory sampler (the later runs have it). WebGPU on integrated GPUs, Apple, Firefox, Safari, mobile: not tested. HF measured on a stand-in file; R2 not tested. Cold-start time on a slow link is arithmetic. The M1 model and the 1.7B model were not run in the browser.
