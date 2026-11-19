# M1 (SFT 0.6B Q8_0) vs B0 on final dev v1

Dev only. Wilson 95% intervals; failed/invalid/errored episodes count as failures.

| System | overall | 1 family | 2 families | 3 families | 4 families | ambiguous | unsupported |
|---|---|---|---|---|---|---|---|
| B0 | 178/300 = 59% [54%, 65%] | 60/72 = 83% [73%, 90%] | 79/127 = 62% [54%, 70%] | 31/71 = 44% [33%, 55%] | 8/30 = 27% [14%, 44%] | 0/2 = 0% [0%, 66%] | 9/9 = 100% [70%, 100%] |
| M1 | 293/300 = 98% [95%, 99%] | 71/72 = 99% [93%, 100%] | 125/127 = 98% [94%, 100%] | 68/71 = 96% [88%, 99%] | 29/30 = 97% [83%, 99%] | 2/2 = 100% [34%, 100%] | 9/9 = 100% [70%, 100%] |

End reasons: B0: {'finish': 169, 'unsupported': 131}; M1: {'asked': 2, 'finish': 282, 'run_budget': 7, 'unsupported': 9}
