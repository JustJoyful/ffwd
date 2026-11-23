# MLC q4f16_1 parity on 100 dev tasks (23 Nov 2026)

Dev only; no test split touched. Same seeded 100-task sample, prompt, harness, run budget and greedy decoding (512 tokens) as the GGUF curve (`reports/2026-11-23-m3-quant-curve`). Produced by a delegated agent; the headline numbers were re-checked against `results.jsonl` and `logit-probe-m3.json` by the main session (2/100, 5/100, 98/100; McNemar p recomputed from the discordant counts).

## Read this first: what was and was not run

**MLC's own runtime was not run.** The nightly `mlc-llm`/`mlc-ai` wheel pair could not compile a model library (details in `toolchain/`). The "MLC" rows below are the **converted MLC weights read back into numpy and run through HF fp16** in the same harness. The read-back is exact: re-quantising the original weights reproduces MLC's stored words and scales 100%, and q0f16 is bit-identical to the source. It exercises every number a WebGPU kernel would dequantise; kernel rounding and the WebLLM runtime are not covered. WebLLM and a real browser were not exercised either. So the result is for the stored weights, not for a measured browser run.

## Results

| model / format | success | invalid-action episodes | mean runs (98 graded) | needless-or-fail (13 copy-eligible) | first turn identical to Q8_0 |
|---|---|---|---|---|---|
| M3 Q8_0 (reference) | 97/100 | 0 | 1.133 | 0/13 | 100% |
| **M3 MLC q4f16_1** | **2/100** [0.6, 7.0] | **80** | 0.837 | 13/13 | 1% |
| M3 MLC q0f16 (control) | 98/100 [93.0, 99.4] | 0 | 1.102 | 0/13 | 88% |
| M1 Q8_0 (reference) | 98/100 | 0 | 1.112 | 5/13 | 100% |
| **M1 MLC q4f16_1** | **5/100** [2.2, 11.2] | **76** | 0.898 | 13/13 | 0% |

"Mean runs" and "needless-or-fail" look fine for q4f16_1 only because it fails before it runs anything. For scale, the M3 GGUF curve is Q8_0 97, Q6_K 99, Q5_K_M 97, Q4_K_M 60.

Paired against the Q8_0 run (exact McNemar):

| | only Q8_0 passes | only MLC passes | p | MLC minus Q8_0 |
|---|---|---|---|---|
| M3 q4f16_1 | 95 | 0 | 5.0e-29 | -95 pp, CI [-99, -90] |
| M1 q4f16_1 | 93 | 0 | 2.0e-28 | -93 pp, CI [-98, -88] |
| M3 q0f16 (control) | 0 | 1 | 1.0 | +1 pp, CI [0, +3] |

**Conclusion:** q4f16_1 breaks both models. q0f16 is lossless, so conversion, tokenizer and prompt handling are fine; the damage is quantisation.

## Why it breaks

Turn-level taxonomy, M3 (turns):

| outcome | Q8_0 (306) | Q4_K_M (426) | MLC q4f16_1 (739) |
|---|---|---|---|
| ok | 290 | 213 | 33 |
| malformed JSON | 0 | 16 | 155 |
| schema-invalid spec | 0 | 32 | 127 |
| run before a valid spec | 0 | 40 | 328 |
| allowlist-rejected command | 0 | 31 | 32 |
| run failed | 7 | 39 | 36 |
| check failed | 9 | 55 | 12 |
| other harness error | 0 | 0 | 16 |

50 of 100 episodes loop on one or two identical invalid replies until the 8-turn budget. Corrupted tokens (M3: `codec not allowed: video`, `vcrop`, `-metadata:s:v` taking a flag as its value; M1: `h264_quet`, `devconv`, `paletten`, `rot`) are the same signature as Q4_K_M's `-xvercode` / `-xmp`. Per-turn detail: `M3-mlc-q4f16_1.parity.json`, `M1-mlc-q4f16_1.parity.json`.

Teacher-forced logit probe, 12 tasks, 1,494 tokens (`logit-probe-m3.json`; localises the damage, does not rank formats):

| weights | top-1 agreement | mean NLL |
|---|---|---|
| original merged fp16 | 99.8% | 0.0128 |
| MLC q4f16_1, everything | 95.9% | 0.158 |
| MLC q4 layers, original embedding / lm_head | 95.4% | 0.142 |
| original layers, MLC q4 embedding / lm_head | 99.6% | 0.0133 |

The damage is in the transformer layers. Keeping the embedding/head in fp16 would not help. Relative weight RMSE is about 0.10 per matrix. Compared with GGUF Q4_K_M (embedding and part of `attn_v`/`ffn_down` at Q6_K, scale-plus-minimum blocks elsewhere), q4f16_1 is symmetric round-to-nearest, group 32, all tensors at 4 bits: Q4_K_M sits at the cliff edge, q4f16_1 is past it. `q4f32_1` was not tested; its body quantisation is the same.

## Prompt identity

11 fixtures (first turns of 10 sample tasks plus one 6-message multi-turn transcript), compared as token ids against HF `apply_chat_template` with our jinja template.

| renderer | identical |
|---|---|
| llama-server `/apply-template` + `/tokenize` | 11/11 |
| MLC stock `qwen3` template | **0/11** (no `<think>\n\n</think>\n\n` in the generation prompt or earlier assistant turns) |
| MLC patched `conv_template` | **11/11**, also when tokenized piece by piece as WebLLM does |

The patch lives in `mlc-chat-config.json` (`role_templates.assistant`, `role_empty_sep`, `strip_reasoning_in_history=false`, `system_message` from `system-v1.txt`); `toolchain/conv_template.patched.json`. WebLLM source was read, not run: it applies `role_templates` to history and has no reasoning-stripping, so patch the template and do not use `enable_thinking`.

## Toolchain status (`toolchain/`)

Conversion works (venv `data/tools/mlc-venv`, `apache-tvm-ffi==0.1.13.post0` is the only ABI that does not segfault). Compiling a model library failed after three attempts (API skew in `mlc_llm/compiler_pass`, then a TVM `StorageRewrite` failure on a sampler kernel); the stable 0.20.0 pair also failed. Unblock options: a newer nightly pair, or skip local compile and load our converted weights with WebLLM's hosted `Qwen3-0.6B-q0f16_cs1k-webgpu.wasm` (library depends on architecture, quantisation and context size, not weights) via a custom `AppConfig`. **Risk to check first:** the prebuilt entries use `context_window_size: 4096`; the first prompt is about 1,400 tokens and episodes grow.

## WebGPU feasibility (Playwright Chromium, RTX 3050 6 GB; `toolchain/webgpu_probe.mjs`)

`navigator.gpu` needs a secure context (the probe serves a stub page on `http://localhost:4321/`). Headed with no flags, or headless with `--enable-unsafe-webgpu --enable-features=Vulkan --use-angle=vulkan`, gives the NVIDIA adapter with `shader-f16`. The flags from the research notes alone give a SwiftShader software adapter with no f16. Limits: `maxBufferSize` 4 GiB, `maxStorageBufferBindingSize` 2 GiB. Guard for any browser harness: assert adapter architecture is not `swiftshader` and `shader-f16` is present. No model was loaded in WebGPU.

## Sizes (`data/mlc/`, untracked)

| path | size |
|---|---|
| `m3-q4f16_1`, `m1-q4f16_1` | 331 MB each (335,372,288 weight bytes, 4.50 bits/param) |
| `m3-q0f16` | 1.2 GB (1,192,099,840 bytes) |

## Limits

100 dev tasks, one seed, greedy. Runtime and kernels not exercised. GPTQ/AWQ-style, mixed-precision and quantisation-aware fine-tuning were not tested (the prebuilt WebLLM libraries do not support them anyway). Patches to the nightly wheels exist in the venv only; diffs are in `toolchain/`.

## Options (owner's decision, nothing decided here)

1. Browser model on `q0f16` (about 1.19 GB download, WebLLM lists about 2.2 GB VRAM) with the prebuilt library and patched config; check the longest dev episode against 4,096 tokens first.
2. For a smaller download: quantisation-aware fine-tuning (train with 4-bit group-32 fake quantisation, export `q4f16_1`). A training change that needs its own plan.
3. First end-to-end browser parity run: Playwright (headed or `--use-angle=vulkan`) on the same 100 tasks with q0f16 weights.
