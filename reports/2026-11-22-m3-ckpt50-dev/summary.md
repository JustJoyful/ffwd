# M3 candidate: main run checkpoint-50 vs M1 and the shuffled-reward control (dev, informational)

Dev only. Wilson 95% intervals; failed/invalid/errored episodes count as failures.

| System | overall | 1 family | 2 families | 3 families | 4 families | ambiguous | unsupported |
|---|---|---|---|---|---|---|---|
| M1 | 293/300 = 98% [95%, 99%] | 71/72 = 99% [93%, 100%] | 125/127 = 98% [94%, 100%] | 68/71 = 96% [88%, 99%] | 29/30 = 97% [83%, 99%] | 2/2 = 100% [34%, 100%] | 9/9 = 100% [70%, 100%] |
| control | 294/300 = 98% [96%, 99%] | 71/72 = 99% [93%, 100%] | 126/127 = 99% [96%, 100%] | 68/71 = 96% [88%, 99%] | 29/30 = 97% [83%, 99%] | 2/2 = 100% [34%, 100%] | 9/9 = 100% [70%, 100%] |
| ckpt50 | 290/300 = 97% [94%, 98%] | 69/72 = 96% [88%, 99%] | 124/127 = 98% [93%, 99%] | 67/71 = 94% [86%, 98%] | 30/30 = 100% [89%, 100%] | 2/2 = 100% [34%, 100%] | 9/9 = 100% [70%, 100%] |

End reasons: M1: {'asked': 2, 'finish': 282, 'run_budget': 7, 'unsupported': 9}; control: {'asked': 2, 'finish': 283, 'run_budget': 5, 'turn_budget': 1, 'unsupported': 9}; ckpt50: {'asked': 2, 'finish': 279, 'run_budget': 10, 'unsupported': 9}

Material spec error rate (container, resolution, time range, lossless, requested codec; lower is better):

| System | rate | by field |
|---|---|---|
| M1 | 72/280 = 26% [21%, 31%] | {'time.end_s': 36, 'video.width': 18, 'video.height': 15, 'container': 7, 'audio.codec': 6, 'time.start_s': 5, 'lossless': 5} |
| control | 69/280 = 25% [20%, 30%] | {'time.end_s': 34, 'video.width': 19, 'video.height': 16, 'container': 8, 'lossless': 5, 'time.start_s': 4, 'audio.codec': 3, 'no_spec': 1} |
| ckpt50 | 68/280 = 24% [20%, 30%] | {'time.end_s': 36, 'video.width': 18, 'video.height': 13, 'container': 8, 'lossless': 5, 'time.start_s': 4, 'audio.codec': 2} |
