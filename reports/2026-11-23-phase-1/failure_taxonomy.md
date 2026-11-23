# Failure taxonomy (descriptive, pooled over test-iid + test-phrasing + test-compositional)

Rows are failed episodes by the kind of task and how the episode ended. `run_budget` = used all runs without a passing check; `turn_budget` = ran out of turns (includes repeated invalid actions); `asked` / `unsupported` = the system stopped to ask or refuse when that was the wrong move for the task kind. Tasks where the right move was to ask or refuse are scored by the same success rule as the rest.

| System | task kind | ended | failed | of tasks of that kind |
|---|---|---|---|---|
| B0 | ambiguous | unsupported | 34 | 34 |
| B0 | supported | unsupported | 331 | 834 |
| B2 | ambiguous | turn_budget | 34 | 34 |
| B2 | supported | turn_budget | 834 | 834 |
| B2 | unsupported | turn_budget | 32 | 32 |
| M1 | ambiguous | unsupported | 4 | 34 |
| M1 | supported | run_budget | 26 | 834 |
| M1 | supported | turn_budget | 2 | 834 |
| M1 | supported | unsupported | 1 | 834 |
| M1 | unsupported | turn_budget | 1 | 32 |
| M3 | ambiguous | turn_budget | 1 | 34 |
| M3 | ambiguous | unsupported | 5 | 34 |
| M3 | supported | run_budget | 24 | 834 |
| M3 | supported | turn_budget | 2 | 834 |
| M3 | supported | unsupported | 1 | 834 |
| X1 | ambiguous | asked | 4 | 34 |
| X1 | ambiguous | unsupported | 1 | 34 |
| X1 | supported | run_budget | 7 | 834 |
| X1 | supported | turn_budget | 19 | 834 |
| X1 | unsupported | run_budget | 1 | 32 |
| X1 | unsupported | turn_budget | 1 | 32 |
| X1 | unsupported | unsupported | 1 | 32 |
