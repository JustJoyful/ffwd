# M3 GGUF quantisation curve on 100 dev tasks, and why Q4_K_M failed (23 Nov 2026)

Dev only, nothing here touches a test split. Same seeded sample, prompt, chat template, harness, run budget and greedy decoding as `reports/2026-11-22-m3-q4km-parity`. Every quant is made from the same f16 GGUF with the same llama.cpp b12032 `llama-quantize`; Q8_0 is the published dev run restricted to the sample. Runs: `reports/2026-11-22-m3-q4km-parity` (Q4_K_M), `reports/2026-11-23-m3-q5km-parity`, `reports/2026-11-23-m3-q6k-parity`. Code: `eval/quant_parity.py --quant`.

| quant | file | success | invalid-action episodes | mean runs (98 graded) | needless-or-fail (13 copy-eligible) | first turn identical to Q8_0 |
|---|---|---|---|---|---|---|
| Q4_K_M | 379 MB | 60/100 | 12 | 1.87 | 5/13 | 30% |
| Q5_K_M | 424 MB | 97/100 | 0 | 1.14 | 0/13 | 54% |
| Q6_K | 473 MB | 99/100 | 0 | 1.08 | 0/13 | 60% |
| Q8_0 | 610 MB | 97/100 | 0 | 1.13 | 0/13 | 100% |

The decision rule in `RULE.md` (written before the Q4_K_M run) passes for Q5_K_M and Q6_K and fails for Q4_K_M. With n = 100 a difference of 2 tasks is noise (Wilson 95% about ±5 pp): Q5_K_M, Q6_K and Q8_0 are indistinguishable here; Q4_K_M is not (37 tasks that only Q8_0 passes, none the other way).

## Is Q4_K_M's loss a conversion, template or tokenizer problem?

No. Two pieces of evidence:
1. **Same pipeline, different outcome.** Q8_0, Q6_K and Q5_K_M are all produced from the same f16 GGUF through the same chat template and tokenizer, and all score 97 to 99. A template or tokenizer fault would hit all of them.
2. **The failures look like noise, not a systematic error.** Turn-level on the 100 tasks (306 turns for Q8_0, 426 for Q4_K_M): Q8_0 has 299 clean turns and 7 failed runs; Q4_K_M has 268 clean turns, 16 malformed-JSON replies, 32 schema-invalid specs, 40 runs sent before a valid spec, and 70 rejected or failed runs. The rejected commands carry corrupted tokens (`-xvercode`, `-xmp`, `paletteode`, `libmp3`, `--rotate=180` inside `-metadata`), 5 of them the forbidden `-y`. That is the signature of a small model losing precision on token choice, not of a wrong prompt.

So: quantisation damage, with a cliff between Q4_K_M and Q5_K_M on this model. Not tested: Q4_K_M with an importance matrix, Q4_K_S, or per-tensor overrides.

## What this means for the browser

MLC `q4f16_1` is a plain 4-bit group quantisation (group size 32, fp16 scales; 4.5 bits per weight by construction), probably at least as aggressive as Q4_K_M, though that is unverified. This result is a strong warning for it, not a prediction: it has to be measured on this same sample (see `reports/2026-11-23-mlc-parity` once written). If it fails, the prebuilt `q0f16` (unquantised, about 1.2 GB download) is the fallback, since there is no prebuilt 5- or 6-bit MLC format.

## What did not change

The Phase 1 test run used Q8_0 and its numbers are untouched. Q6_K or Q5_K_M as the native shipping format is an owner decision (about 20% smaller than Q8_0, same dev accuracy within noise); nothing is decided here. Dev sample only, one model, one seed.
