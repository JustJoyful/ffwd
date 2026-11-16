# Dev baselines on spike-free dev v1 (n=300)

Dev only. Wilson 95% intervals; failed/invalid/errored episodes count as failures.

| System | overall | 1 family | 2 families | 3 families | 4 families | ambiguous | unsupported |
|---|---|---|---|---|---|---|---|
| B0 | 158/300 = 53% [47%, 58%] | 38/44 = 86% [73%, 94%] | 79/129 = 61% [53%, 69%] | 35/107 = 33% [25%, 42%] | 6/20 = 30% [15%, 52%] | 0/2 = 0% [0%, 66%] | 5/5 = 100% [57%, 100%] |
| B2-qwen3-0.6b | 0/300 = 0% [0%, 1%] | 0/44 = 0% [0%, 8%] | 0/129 = 0% [0%, 3%] | 0/107 = 0% [0%, 3%] | 0/20 = 0% [0%, 16%] | 0/2 = 0% [0%, 66%] | 0/5 = 0% [0%, 43%] |

End reasons: B0: {'finish': 153, 'unsupported': 147}; B2-qwen3-0.6b: {'turn_budget': 300}

## Interpretation
- **B2 (stock Qwen3-0.6B, prompt v1, spec-first) passes 0/300 [0%, 1%].** All 300 episodes used all 8 turns as invalid turns, with no `"action"` key ever emitted, no spec accepted, no run attempted. It writes `{"spec": {...}}` instead of `{"action": "spec", ...}`. So the base model cannot follow the action protocol; this is the floor SFT must lift, not a measure of FFmpeg skill.
- **B0 (regex baseline) passes 158/300 = 53% [47%, 58%].** It is strong on 1-family tasks (86%) and decays with composition (61% / 33% / 30% for 2/3/4 families), and it never asks (0/2 ambiguous) while refusing unsupported correctly (5/5). Overall 147 of its 300 episodes ended `unsupported`; it declines whenever no pattern matches.
- **Takeaway:** the bar for the trained model on dev v1 is 53% overall and 33% on 3-family tasks. n is small for ambiguous (2) and unsupported (5), so those columns are not evidence. Dev only; no test split was touched.
