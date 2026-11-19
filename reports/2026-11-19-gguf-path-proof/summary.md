# GGUF path proof on base Qwen3-0.6B (19 Nov 2026), D-036

Path: HF snapshot `Qwen/Qwen3-0.6B@c1899de2...` -> `convert_hf_to_gguf.py` (llama.cpp **b12032**, commit `dde879bc...`, own venv) -> f16 GGUF (1509 MB) -> `llama-quantize` Q8_0 (761.8 MiB, 8.5 bpw) -> `llama-server` b12032 (Vulkan, RTX 3050 6 GB, `--jinja -ngl 99 -c 8192 -np 1 --cache-ram 0 --seed 20261115`) -> `eval.run_baseline --system B2` on the first 5 dev v1 tasks, harness + checker unchanged.

| model | tasks | pass | invalid turns | result |
|---|---|---|---|---|
| converted Q8_0 (sha256 `7cb85262...c9f77`) | 5 | 0/5 | 8/8 turns each | `B2-converted-5/` |
| official `Qwen3-0.6B-Q8_0.gguf` (sha256 `9465e63a...b031`) | same 5 | 0/5 | 8/8 turns each | `B2-stock-5/` |

0/5 is the expected score of an untrained base model (it writes `{"spec": ...}` without `"action"`, as in the 300-task B2 baseline); what this proves is that every stage runs and the harness talks to the converted file. The two models' replies are **not byte-identical** (ours goes through an f16 intermediate, the official file was built differently); both fail the same way on all 5 tasks. A numeric check of a fine-tuned model (HF vs GGUF first-token agreement, `eval/parity.py` metrics) belongs with M1.

Not re-run: B0 on the final dev split. It was run on 19 Nov on the frozen code (`eval/b0_regex.py` has had no commit since `cfb2ab7`): **178/300 = 59% [54%, 65%] Wilson 95%**; 1 family 51/61 = 84% [72%, 91%], 2 families 79/127 = 62% [54%, 70%], 3 families 31/71 = 44% [33%, 55%], 4 families 8/30 = 27% [14%, 44%], ambiguous 0/2, unsupported 9/9 (`reports/2026-11-19-phase1-dev-baselines-protocol03/summary.md`). The bar for M1 on final dev.

Tooling versions are in `manifest.json`.
