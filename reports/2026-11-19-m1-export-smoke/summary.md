# M1 export path smoke test (19 Nov 2026): 3 SFT steps -> merge -> GGUF -> llama-server -> harness

Purpose: prove every step between a trained adapter and an M1 dev result BEFORE the real SFT finishes. The model here is garbage on purpose (3 optimizer steps on 900 partial-bulk trajectories + 341 oracle ones, eval loss 0.77); the score is not a result.

| step | result |
|---|---|
| `refilter` + `oracle` on a copy of the partial bulk data | 841 kept of 900 episodes; 343 oracle episodes (341 passed; 170 unsupported top-ups) |
| `training.sft.build` | 1101 train + 81 val examples; 265 invalid-turn pairs removed; 0 dropped for length; mean 1738 tokens, max 2921 |
| `training.sft.train --max-steps 3` (local RTX 3050) | runs; ~1000 tokens/s, so a full local run would take hours: Kaggle is the place |
| `training.export.merge` | works, but transformers 5 wrote `extra_special_tokens` as a list and the converter env (transformers 4.57.6, the tag's own pin) crashed. **Fixed in `merge.py`** (`converter_compatible_tokenizer`, tested) |
| `to_gguf` (b12032 converter + quantize, own venv) | f16 -> Q8_0, 639 MB |
| `llama-server` + `--chat-template-file chat-template.jinja` + `eval.run_baseline --system M1` | 5 dev tasks run end to end; 0/5, 4 tasks 8 invalid turns (the model writes `{"spec":..., "run":...}` without `"action"`), as expected after 3 steps |

One episode ended `error`: `request (4210 tokens) exceeds the available context size (4096 tokens)`. The M1/M3 configs had `-c 4096`, the baselines use `-c 8192`. A long episode must not fail because of the server's context while the baselines are not limited by it, so `m1-0.6b-q8.toml` and `m3-0.6b-q8.toml` now use `-c 8192` (same as every baseline; SFT streams are at most 3072 tokens).
