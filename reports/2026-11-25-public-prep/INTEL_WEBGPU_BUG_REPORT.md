# wllama 4.0.0 / ggml-webgpu: wrong output (repeated garbage tokens) on Intel gen-12lp when the prompt is longer than about 880 tokens

Ready to post by the owner; nothing has been posted. Attach `intel-webgpu-repro-prompt.txt` (the exact 1333-token prompt).

## Summary

With wllama 4.0.0 (libllama b12637-0b51bb2) in Chromium 159 on an Intel UHD (Alder Lake-S, gen-12lp, Mesa ANV), a greedy completion on the WebGPU backend returns repeated garbage tokens ("болболбол...", ",,,,,", "Solution Solution ...") when the prompt is long. The same model file, prompt and settings give the correct reply on the same machine's NVIDIA GPU through WebGPU, on the CPU (wasm) backend, and on native llama.cpp b12032. Prompts of 774 and 837 tokens give the correct reply on the Intel adapter; prompts of 881, 950, 1176 and 1333 tokens give garbage. The first generated token is already wrong.

## Environment

| | |
|---|---|
| wllama | 4.0.0 (npm) |
| libllama inside it | b12637-0b51bb2 (`Wllama.getLibllamaVersion()`) |
| Browser | Chromium 159.0.8154.6 (Playwright 1.65.1 `channel: "chromium"`, headless), flags `--enable-unsafe-webgpu --enable-features=Vulkan --use-angle=vulkan` |
| OS | CachyOS (Arch based), kernel 7.2.9-2-cachyos |
| Mesa / Vulkan | mesa 26.2.4-1, vulkan-intel 26.2.4-1 (`driverInfo = Mesa 26.2.4-arch3.1`), vulkan-icd-loader 1.4.363.0-1.1; Vulkan API 1.4.354 on the Intel device |
| Adapter (`requestAdapter().info`) | vendor `intel`, architecture `gen-12lp`, description `""` (empty), `isFallbackAdapter: false`; features include `shader-f16`, `subgroups`, `subgroup-size-control`; maxBufferSize 4294967292 |
| Device | Intel(R) UHD Graphics (ADL-S GT0.5), shares system RAM. Only the Intel Vulkan ICD was made visible (`VK_ICD_FILENAMES` and `VK_DRIVER_FILES` set to Mesa's `intel_icd.json`) so the page cannot pick the NVIDIA GPU |
| Runtime log | `ggml_webgpu: adapter_info: vendor: intel | architecture: gen-12lp`, `offloaded 29/29 layers to GPU`, `layer 0 is assigned to device WebGPU but Flash Attention over K/V rows is assigned to device CPU (usually due to missing support)` |
| Model | Qwen3-0.6B fine-tune (agent model), GGUF Q5_K_M, 444,411,456 bytes, sha256 `bbf439b749c02c04b5227ab93fb1430263a7c567c15552b6e12ae3836cde1e11`. A Q8_0 file of the same model also gives garbage (see below). The model is a fine-tune that is not yet public; the behaviour has NOT been tried on a public model. |
| Load options | `n_ctx 8192`, `n_gpu_layers 999`, `cache_type_k/v q8_0`, `flash_attn true`, `n_threads 4`; completion: `temperature 0`, `max_tokens 20`, `seed 1` |

## The prompt (canary)

A Qwen3 chat-format string built outside the runtime and passed as a plain-text completion (the runtime's own chat template is not used): `<|im_start|>system\n{system prompt}<|im_end|>\n<|im_start|>user\n{one JSON line}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n`. It is 1333 tokens. The exact text (4,856 characters, 1333 tokens, no private content) is attached as `intel-webgpu-repro-prompt.txt`; pass it as a plain-text completion, do not apply a chat template to it. It is the system prompt of an FFmpeg-agent protocol followed by a request to cut 2 seconds off a video clip. The 774 to 1176 token variants were made by dropping system-prompt paragraphs.

## Expected and actual

Expected (native llama.cpp b12032, CPU, greedy; identical on NVIDIA WebGPU and on wllama CPU, 20 of 20 token ids):

```
{"action": "spec", "spec": {"family": ["F1"], "outputs": [{"
```

ids: 4913 1311 788 330 9535 497 330 9535 788 5212 18984 788 4383 37 16 7914 330 41006 788 61753

Actual on Intel gen-12lp WebGPU, three full runs of the 1333-token prompt, each with 0 of 20 ids matching:

```
болболболболболболболболболболболболболболболболболболболбол
```

ids: 125302 125302 125302 ... (the same id repeated). Earlier runs with the full chat prompts gave `$",,,,,,,,,` and `,,,,,,,,` (Q5_K_M, f16 KV) and `Solution Solution Solution ...` (Q8_0 weights, f16 KV).

## Measured by prompt length (same model, same settings, Intel adapter, one cold run each)

| prompt tokens | ids matching the native reply (of 20) | prompt tok/s | generation tok/s |
|---|---|---|---|
| 774 | 20 (and 20 on the repeat) | 23.0 | 5.1 |
| 837 | 20 | 21.5 | 4.8 |
| 881 | 0 | 21.1 | 24.4 |
| 950 | 0 | 46.4 | 27.3 |
| 1176 | 0 | 19.6 | 26.6 |
| 1333 | 0 (three runs) | 32 to 64 | 21 to 25 |

Two things in this table are unexplained: (1) the threshold lies between 837 and 881 tokens and nothing here explains why; (2) the correct runs generate at about 5 tok/s and the garbage runs at about 21 to 27 tok/s, which looks like a different pipeline or kernel path being taken, not a slow-but-right one. Both are observations, not a diagnosis.

For comparison on the same machine: NVIDIA GeForce RTX 3050 6GB (driver 615.78.08) through the same WebGPU path: 20 of 20 at 774 and 1333 tokens (prompt 312 to 361 tok/s, generation 54 to 56 tok/s); wllama CPU (4 threads): 20 of 20 at both lengths.

## Configurations already tried on the Intel adapter (all garbage; the first five were run earlier in the same project)

1. Q5_K_M, q8_0 KV cache + flash attention (the frozen configuration), full 100-task run: 4 of 4 tasks ended with garbage.
2. Q5_K_M, q8_0 KV + flash attention, Mesa shader cache disabled: "болбол..." repeated.
3. Q5_K_M, f16 KV cache (two runs): commas and symbols.
4. Q5_K_M, f16 KV cache, Mesa shader cache disabled: commas and symbols.
5. Q8_0 weights, f16 KV cache: "Solution Solution Solution...".
6. (this session) Q5_K_M, q8_0 KV + FA, the 1333-token canary prompt, three runs, 0 of 20 each, and the length bisection above.

## Ruled out (by these runs)

- KV cache type (q8_0 vs f16): garbage in both.
- Weight quantisation (Q5_K_M vs Q8_0): garbage in both.
- Mesa's on-disk shader cache: garbage with it disabled.
- The model file and prompt: the same file and prompt are right on NVIDIA WebGPU, on wllama CPU and on native llama.cpp.
- The harness: the same page, driver code and flags give correct output on the NVIDIA adapter.

Prompt length is NOT ruled out; it is the strongest correlate (table above).

## Not established

- The root cause: which kernel or shader is wrong, and whether it is in ggml-webgpu, in Dawn's Vulkan backend, in Mesa ANV for gen-12lp, or in how the runtime splits the batch (n_batch 2048; n_ubatch was not changed or tested).
- Whether the cut-off is a token count, a batch or ubatch boundary, or an allocation size (the log says flash attention runs on the CPU for layer 0; whether that matters was not tested).
- Whether other Intel generations, other Mesa versions, Chrome stable (this is Chromium 159 from Playwright), Firefox or Windows drivers show it. Only this one adapter and driver were tested.
- Whether a public model reproduces it.
- A clean "flash attention off" long-prompt run: the q8_0 V cache needs flash attention, and the f16 runs used the default.

## Minimal repro recipe for someone else

Needs an Intel gen-12lp GPU (Alder Lake UHD tested) with Mesa ANV, and a Chromium with WebGPU enabled. Steps 1 to 3 are what was run here; the public-model variant in step 4 has NOT been run.

1. `npm i @wllama/wllama@4.0.0` and serve a page that is cross-origin isolated (COOP `same-origin`, COEP `require-corp`) so multithreading works.
2. Launch Chromium with `--enable-unsafe-webgpu --enable-features=Vulkan --use-angle=vulkan`. To make sure the page cannot pick another GPU, point `VK_ICD_FILENAMES` and `VK_DRIVER_FILES` at Mesa's `intel_icd.json` only.
3. Load the GGUF with `n_ctx 8192`, `n_gpu_layers 999`, `cache_type_k` and `cache_type_v` `q8_0`, `flash_attn true`, `n_threads 4`. Run a plain-text completion of the attached prompt with `temperature 0`, `max_tokens 20`, `seed 1`, and compare the 20 token ids with the expected ids above. Repeat after truncating the prompt to under about 840 tokens (drop paragraphs from the system part) to see the correct reply on the same adapter.
4. Public-model variant (untested): use the Q8_0 GGUF from the official `Qwen/Qwen3-0.6B-GGUF` repository with any plain-text prompt of 900 to 1400 tokens, and compare the same completion on the CPU backend (set `n_gpu_layers 0`) with the Intel WebGPU one. If the CPU and WebGPU text differ and the output is a repeated token, it is the same symptom. A prompt that long needs no special content.

## Where it probably belongs

Most likely `ggml-webgpu` in `ggml-org/llama.cpp` (wllama 4.0.0 embeds b12637); `ngxson/wllama` if its maintainers think the glue (device request, limits, batch settings) is at fault. Dawn or Mesa ANV are possible, but that would need a reproduction without llama.cpp, which was not made.

## Duplicate search (quick, 25 Nov 2026, web search only, the trackers' own search boxes were not used)

No issue matching "ggml-webgpu + Intel + wrong output on long prompts" or mentioning wllama was found. Related but different (Vulkan backend, not WebGPU) reports of garbage output on Intel iGPUs with Mesa ANV, which may share a root cause below the backend:

- https://github.com/ggml-org/llama.cpp/issues/19327 (Arrow Lake iGPU, Vulkan, 3B+ models garbage, 1B fine with flash attention off)
- https://github.com/ggml-org/llama.cpp/issues/21888 (Meteor Lake, Mesa ANV, deterministic garbage on Vulkan, correct on CPU)
- https://github.com/ggml-org/llama.cpp/issues/18946 (Lunar Lake Vulkan incompatibilities; not about wrong output)

A search inside `ggml-org/llama.cpp` and `ngxson/wllama` issues for "webgpu intel" and "wllama webgpu garbage" should still be done by the poster just before posting.

## What was not checked

- A native llama.cpp build with the WebGPU backend on this adapter (b12032 was run on the CPU only), which would separate the llama.cpp shaders from the browser stack.
- Whether another Intel generation, Mesa version, Chrome stable, Firefox or a Windows driver shows it.
- Whether a public model reproduces it (step 4).
- Changing `n_batch` or `n_ubatch`, which would test the batch-boundary idea.
