# ffwd-0.6b v1.0.0

A 0.6B FFmpeg agent: Qwen3-0.6B fine-tuned with SFT and multi-turn GRPO (checkpoint-60 of a 60-step run) to turn a plain-language video chore ("cut the first 3 seconds", "make this a GIF") into a verified FFmpeg command. It emits one JSON action per turn (`spec`, `ask_user`, `unsupported`, `run`, `finish`) inside a harness that checks every run. The model card is `README.md`; the manifest apps read is `ffwd-model.json`.

## Results (generated held-out tasks, 900 across the three test splits; read the card's Limitations)

- **95.0% (855/900) in the browser** (the shipped file, Q5_K_M, wllama 4.0.0 on WebGPU, q8_0 KV cache, `n_ctx` 8192).
- **Native Q8_0 (the evaluated headline file): 96.3% (867/900).**
- Paired difference, browser minus native Q8_0: **-1.33 pp, 95% CI [-2.67, -0.11]**. The preregistered guard (lower bound above -2.0 pp) is **not shown** for the browser row. The row is descriptive; no p-value and no efficiency claim is made for it.
- Generated tasks are not real user clips; one training seed per system; the shipped format is below the evaluated one. Other quantisations: Q4_K_M scored 60/100 on the dev sample (do not use it).

## Files (verify with `sha256sum -c SHA256SUMS`)

| file | role | bytes | sha256 |
|---|---|---|---|
| `ffwd-0.6b-v1.0.0-Q5_K_M.gguf` | shipped | 444,411,456 | `bbf439b749c02c04b5227ab93fb1430263a7c567c15552b6e12ae3836cde1e11` |
| `ffwd-0.6b-v1.0.0-Q8_0.gguf` | evaluated (Phase 1 headline) | 639,443,520 | `0fa2333c66e4b8697465e5753f4ef4b8ada40ee3f77a234659afb223e382e1b1` |

Both are byte-identical to the files that were evaluated (copied, never re-quantised). `ffwd-model.json` also lists the system prompt (`system-v1.txt`, sha256 `56e7d721...`), the chat template (`chat-template.jinja`, sha256 `8d12c213...`), the runtime defaults and the WebGPU canary. The LoRA adapter (`adapter/`, Hugging Face only) is not a GitHub asset.

## Run it with llama.cpp

The agent chat template is required: use `chat-template.jinja`, not the stock Qwen3 template (stock templates drop the empty think block from earlier assistant turns, which this model was never trained on), and do not pass `chat_template_kwargs` or `enable_thinking`. The system prompt is the content of `system-v1.txt`.

```
llama-server -m ffwd-0.6b-v1.0.0-Q5_K_M.gguf \
  --jinja --chat-template-file chat-template.jinja \
  -ngl 99 -c 8192 -np 1 --cache-ram 0 --seed 20261115 \
  -ctk q8_0 -ctv q8_0 -fa on \
  --host 127.0.0.1 --port 8080
```

Request with `temperature` 0 and `max_tokens` 512 on `/v1/chat/completions`. For the evaluated configuration use the Q8_0 file and drop the `-ctk -ctv -fa` flags (the Phase 1 numbers were measured with the f16 KV cache). The protocol loop around the model (spec first, automatic check after every run, at most 4 runs) is in the project repo; the CLI is `uv run python -m apps.cli.ffmpeg_agent_cli "<request>" file.mp4 --model <gguf> --llama-server <path>`.

What was and was not verified for this command (24 Nov 2026, llama.cpp b12032, commit dde879bc4):

- Verified here: the server starts on the packaged Q5_K_M file with every flag above except `-ngl 99` (run with `-ngl 0`, CPU, 4 threads), serves `/health`, and the canary prompt in `ffwd-model.json` returns the expected 20 token ids (20 of 20, text `{"action": "spec", "spec": {"family": ["F1"], "outputs": [{"`) with the q8_0 KV cache and flash attention on.
- Not verified here: `-ngl 99` on a GPU with this exact command line; the Q8_0 file with q8_0 KV; any llama.cpp build other than b12032 (the browser build is b12637 inside wllama 4.0.0); end-to-end jobs through the CLI with this package.
- The CLI as it stands starts its own server with `-c 4096`, f16 KV and no `-ctk/-ctv/-fa` (`apps/cli/ffmpeg_agent_cli/server.py`), so it does not use the shipped runtime defaults of `ffwd-model.json` (8192, q8_0). It has not been changed for this release.

## Licence

The weights are a derivative of Qwen/Qwen3-0.6B and are under Apache-2.0 (`LICENSE`, the Qwen3 text unchanged; the changes made are stated in the card). Project code: GPL-3.0.
