# M3 GGUF Q8_0 vs Q4_K_M on 100 dev tasks (22 Nov 2026, A3): ship Q8_0

Dev only. Same seeded sample as the M1 parity (`random.Random(20261115)`), same prompt, template, harness and run budget, greedy. Q8_0 side = the published dev run of M3 (`reports/2026-11-22-m3-ckpt60-dev`) restricted to the sample; Q4_K_M made from the f16 GGUF with llama.cpp b12032 `llama-quantize` (397 MB against 639 MB). The decision rule was committed before the run (`RULE.md`). Code: `eval/quant_parity.py`; raw results `parity.json`, run `M3-q4km/`.

| | Q8_0 | Q4_K_M |
|---|---|---|
| success | 97/100 = 97% [92, 99] | **60/100 = 60% [50, 69]** |
| episodes with an invalid action | 0 | 12 |
| mean runs per graded task (98) | 1.13 | 1.87 |
| needless-or-fail, copy-eligible (13) | 0/13 | 5/13 = 38% |
| first assistant turn byte-identical to Q8_0 | | 30% |

Paired Q4 - Q8: -37 pp, 95% CI [-47, -28]; 37 tasks only Q8_0 passes, 0 only Q4_K_M passes; exact McNemar p = 1.5e-11. **All four conditions of the rule fail, so Q8_0 ships.**

The failures are model errors, not harness artefacts: 29 end by the 4-run budget (typically a forbidden `-y` flag, which the allowlist rejects, or a wrong command repeated), 11 by the turn budget (malformed JSON or an invalid spec), 0 errored episodes, no timeouts. Q4_K_M visibly damages this 0.6B fine-tune's format discipline (about 5.2 bits per weight on a model this small).

Not tested: other quants (Q5_K_M, Q6_K) or Q4 with an importance matrix, which might sit between the two; the browser MLC q4f16_1 build is the Phase 2 parity question and this result is a warning for it (q4f16_1 is also 4-bit): the browser model must be measured on the same task sample before it is trusted. Caveat: the machine was heavily loaded (several jobs), which does not change greedy outputs and produced no timeouts.
