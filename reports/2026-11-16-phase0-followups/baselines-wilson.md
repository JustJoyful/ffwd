# Baseline results

Success with Wilson 95% CI (D-021); paired differences use a paired bootstrap. Failed, invalid and errored episodes count as failures.

| System | n | success | graded | ambiguous | unsupported | runs/task | invalid turns/task |
|---|---|---|---|---|---|---|---|
| B1-qwen3-0.6b | 50 | 0% [0%, 7%] | 0/44 | 0/3 | 0/3 | 0.00 | 7.30 |
| B1-qwen3-1.7b | 50 | 8% [3%, 19%] | 1/44 | 0/3 | 3/3 | 0.08 | 0.84 |
| B2-qwen3-0.6b | 50 | 0% [0%, 7%] | 0/44 | 0/3 | 0/3 | 0.00 | 7.30 |
| B2-qwen3-1.7b | 50 | 8% [3%, 19%] | 1/44 | 0/3 | 3/3 | 0.08 | 0.84 |
| X1-deepseek-flash | 50 | 94% [84%, 98%] | 42/44 | 2/3 | 3/3 | 1.26 | 0.52 |

## By family (tasks containing the family)

| System | F1 | F2 | F3 | F4 | F5 | F6 | F7 | F8 | F9 | F10 | F11 | F12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1-qwen3-0.6b | 0/10 | 0/4 | 0/8 | 0/8 | 0/4 | 0/5 | 0/4 | 0/4 | 0/4 | 0/3 | 0/3 | 0/5 |
| B1-qwen3-1.7b | 1/10 | 0/4 | 2/8 | 1/8 | 0/4 | 0/5 | 0/4 | 0/4 | 0/4 | 0/3 | 0/3 | 0/5 |
| B2-qwen3-0.6b | 0/10 | 0/4 | 0/8 | 0/8 | 0/4 | 0/5 | 0/4 | 0/4 | 0/4 | 0/3 | 0/3 | 0/5 |
| B2-qwen3-1.7b | 1/10 | 0/4 | 2/8 | 1/8 | 0/4 | 0/5 | 0/4 | 0/4 | 0/4 | 0/3 | 0/3 | 0/5 |
| X1-deepseek-flash | 10/10 | 4/4 | 8/8 | 8/8 | 3/4 | 4/5 | 4/4 | 4/4 | 4/4 | 3/3 | 2/3 | 5/5 |

## Paired differences (percentage points, paired bootstrap 95% CI)

- X1-deepseek-flash − B2-qwen3-0.6b: +94.0 [+86.0, +100.0]
- X1-deepseek-flash − B2-qwen3-1.7b: +86.0 [+76.0, +94.0]
