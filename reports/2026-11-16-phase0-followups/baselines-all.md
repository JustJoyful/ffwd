# Baseline results

Success with Wilson 95% CI (D-021); paired differences use a paired bootstrap. Failed, invalid and errored episodes count as failures.

| System | n | success | graded | ambiguous | unsupported | runs/task | invalid turns/task |
|---|---|---|---|---|---|---|---|
| B0-regex | 50 | 92% [81%, 97%] | 43/44 | 0/3 | 3/3 | 0.88 | 0.00 |
| B1-qwen3-0.6b | 50 | 0% [0%, 7%] | 0/44 | 0/3 | 0/3 | 0.00 | 7.30 |
| B1-qwen3-0.6b-fair | 50 | 0% [0%, 7%] | 0/44 | 0/3 | 0/3 | 0.96 | 0.04 |
| B1-qwen3-1.7b | 50 | 8% [3%, 19%] | 1/44 | 0/3 | 3/3 | 0.08 | 0.84 |
| B1-qwen3-1.7b-fair | 50 | 8% [3%, 19%] | 0/44 | 3/3 | 1/3 | 0.94 | 0.08 |
| B2-qwen3-0.6b | 50 | 0% [0%, 7%] | 0/44 | 0/3 | 0/3 | 0.00 | 7.30 |
| B2-qwen3-0.6b-fair | 50 | 0% [0%, 7%] | 0/44 | 0/3 | 0/3 | 0.96 | 0.04 |
| B2-qwen3-1.7b | 50 | 8% [3%, 19%] | 1/44 | 0/3 | 3/3 | 0.08 | 0.84 |
| B2-qwen3-1.7b-fair | 50 | 8% [3%, 19%] | 0/44 | 3/3 | 1/3 | 1.60 | 0.96 |
| X1-deepseek-flash | 50 | 94% [84%, 98%] | 42/44 | 2/3 | 3/3 | 1.26 | 0.52 |

## By family (tasks containing the family)

| System | F1 | F2 | F3 | F4 | F5 | F6 | F7 | F8 | F9 | F10 | F11 | F12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0-regex | 8/10 | 4/4 | 7/8 | 8/8 | 4/4 | 4/5 | 4/4 | 4/4 | 4/4 | 3/3 | 3/3 | 4/5 |
| B1-qwen3-0.6b | 0/10 | 0/4 | 0/8 | 0/8 | 0/4 | 0/5 | 0/4 | 0/4 | 0/4 | 0/3 | 0/3 | 0/5 |
| B1-qwen3-0.6b-fair | 0/10 | 0/4 | 0/8 | 0/8 | 0/4 | 0/5 | 0/4 | 0/4 | 0/4 | 0/3 | 0/3 | 0/5 |
| B1-qwen3-1.7b | 1/10 | 0/4 | 2/8 | 1/8 | 0/4 | 0/5 | 0/4 | 0/4 | 0/4 | 0/3 | 0/3 | 0/5 |
| B1-qwen3-1.7b-fair | 1/10 | 0/4 | 2/8 | 0/8 | 0/4 | 1/5 | 0/4 | 0/4 | 0/4 | 0/3 | 0/3 | 0/5 |
| B2-qwen3-0.6b | 0/10 | 0/4 | 0/8 | 0/8 | 0/4 | 0/5 | 0/4 | 0/4 | 0/4 | 0/3 | 0/3 | 0/5 |
| B2-qwen3-0.6b-fair | 0/10 | 0/4 | 0/8 | 0/8 | 0/4 | 0/5 | 0/4 | 0/4 | 0/4 | 0/3 | 0/3 | 0/5 |
| B2-qwen3-1.7b | 1/10 | 0/4 | 2/8 | 1/8 | 0/4 | 0/5 | 0/4 | 0/4 | 0/4 | 0/3 | 0/3 | 0/5 |
| B2-qwen3-1.7b-fair | 1/10 | 0/4 | 2/8 | 0/8 | 0/4 | 1/5 | 0/4 | 0/4 | 0/4 | 0/3 | 0/3 | 0/5 |
| X1-deepseek-flash | 10/10 | 4/4 | 8/8 | 8/8 | 3/4 | 4/5 | 4/4 | 4/4 | 4/4 | 3/3 | 2/3 | 5/5 |

## Graded tasks by number of chore families (single-step = 1 family, multi-step = 2+)

| System | single-step | multi-step |
|---|---|---|
| B0-regex | 34/34 | 9/10 |
| B1-qwen3-0.6b | 0/34 | 0/10 |
| B1-qwen3-0.6b-fair | 0/34 | 0/10 |
| B1-qwen3-1.7b | 1/34 | 0/10 |
| B1-qwen3-1.7b-fair | 0/34 | 0/10 |
| B2-qwen3-0.6b | 0/34 | 0/10 |
| B2-qwen3-0.6b-fair | 0/34 | 0/10 |
| B2-qwen3-1.7b | 1/34 | 0/10 |
| B2-qwen3-1.7b-fair | 0/34 | 0/10 |
| X1-deepseek-flash | 32/34 | 10/10 |

## Failure taxonomy (count of FAILED episodes per category; see eval/taxonomy.py)

| System | failed | unparseable | invalid_action | refusal | wrong_command | check_fail | stalled | missed_clarification | false_attempt | unknown_transcript_lost |
|---|---|---|---|---|---|---|---|---|---|---|
| B0-regex | 4 |  |  |  |  | 1 |  | 3 |  |  |
| B1-qwen3-0.6b | 50 | 44 |  |  |  |  |  | 3 | 3 |  |
| B1-qwen3-0.6b-fair | 50 | 2 | 42 |  |  |  |  | 3 | 3 |  |
| B1-qwen3-1.7b | 46 | 1 |  | 39 |  | 3 |  | 3 |  |  |
| B1-qwen3-1.7b-fair | 46 |  | 42 | 2 |  |  |  |  | 2 |  |
| B2-qwen3-0.6b | 50 | 44 |  |  |  |  |  | 3 | 3 |  |
| B2-qwen3-0.6b-fair | 50 | 2 | 14 | 28 |  |  |  | 3 | 3 |  |
| B2-qwen3-1.7b | 46 | 1 |  | 39 |  | 3 |  | 3 |  |  |
| B2-qwen3-1.7b-fair | 46 |  | 37 | 7 |  |  |  |  | 2 |  |
| X1-deepseek-flash | 3 |  |  |  |  | 1 |  | 1 |  | 1 |

## Paired differences (percentage points, paired bootstrap 95% CI)

- X1-deepseek-flash − B2-qwen3-0.6b: +94.0 [+86.0, +100.0]
- X1-deepseek-flash − B2-qwen3-1.7b: +86.0 [+76.0, +94.0]
- X1-deepseek-flash − B0-regex: +2.0 [-6.0, +12.0]
- X1-deepseek-flash − B2-qwen3-0.6b-fair: +94.0 [+86.0, +100.0]
- X1-deepseek-flash − B2-qwen3-1.7b-fair: +86.0 [+74.0, +96.0]
