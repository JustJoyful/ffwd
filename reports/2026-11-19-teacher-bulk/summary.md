# Teacher bulk run `bulk-20261119` (19 Nov 2026)

Ended: **budget**. 3490 episodes on train tasks (of 4472), DeepSeek `deepseek-flash` (DeepSeek-V4.1-Flash-1017), prompt v1 sha256 `56e7d7217b97...`, thinking off.

| measure | result | gate |
|---|---|---|
| kept-rate (checker verdict) | 3372/3490 = 96.6% [96.0%, 97.2%] | >= 82% per chunk of 500 |
| kept after the label filter (SFT input) | 3199/3490 = 91.7% [90.7%, 92.5%] | |
| cost (billed at peak rates) | $2.2968 ($0.00066/episode) | cap $2.30 |
| cache-hit ratio | 84.0% | >= 60% |
| trajectories with an invalid-action turn | 945/3490 = 27.1% [25.6%, 28.6%] (1336 turns, dropped by the SFT builder) | |

## Chunks

| chunk | episodes | kept-rate | label-rejected | chunk $ | running $ | cache-hit | stopped |
|---|---|---|---|---|---|---|---|
| 1 | 500 | 96.8% | 19 | 0.3272 | 0.3272 | 84.2% |  |
| 2 | 500 | 96.8% | 21 | 0.3350 | 0.6623 | 84.2% |  |
| 3 | 500 | 97.4% | 32 | 0.3213 | 0.9836 | 84.1% |  |
| 4 | 500 | 98.6% | 18 | 0.3233 | 1.3069 | 84.1% |  |
| 5 | 500 | 96.8% | 28 | 0.3309 | 1.6378 | 84.1% |  |
| 6 | 500 | 94.6% | 33 | 0.3384 | 1.9762 | 84.1% |  |
| 7 | 490 | 95.3% | 41 | 0.3206 | 2.2968 | 84.0% | budget: run cap $2.30 would be exceeded |

## Per family: every task that contains the family (checker verdict; `kept` = after the label filter)

| family | n | passed | kept |
|---|---|---|---|
| F1 | 1403 | 1348/1403 = 96.1% [94.9%, 97.0%] | 1348/1403 = 96.1% [94.9%, 97.0%] |
| F2 | 285 | 284/285 = 99.6% [98.0%, 99.9%] | 284/285 = 99.6% [98.0%, 99.9%] |
| F3 | 380 | 359/380 = 94.5% [91.7%, 96.4%] | 359/380 = 94.5% [91.7%, 96.4%] |
| F4 | 948 | 930/948 = 98.1% [97.0%, 98.8%] | 930/948 = 98.1% [97.0%, 98.8%] |
| F5 | 446 | 422/446 = 94.6% [92.1%, 96.4%] | 422/446 = 94.6% [92.1%, 96.4%] |
| F6 | 247 | 236/247 = 95.5% [92.2%, 97.5%] | 236/247 = 95.5% [92.2%, 97.5%] |
| F7 | 135 | 131/135 = 97.0% [92.6%, 98.8%] | 131/135 = 97.0% [92.6%, 98.8%] |
| F8 | 102 | 102/102 = 100.0% [96.4%, 100.0%] | 102/102 = 100.0% [96.4%, 100.0%] |
| F9 | 850 | 824/850 = 96.9% [95.6%, 97.9%] | 824/850 = 96.9% [95.6%, 97.9%] |
| F10 | 279 | 275/279 = 98.6% [96.4%, 99.4%] | 275/279 = 98.6% [96.4%, 99.4%] |
| F11 | 95 | 93/95 = 97.9% [92.6%, 99.4%] | 93/95 = 97.9% [92.6%, 99.4%] |
| F12 | 845 | 811/845 = 96.0% [94.4%, 97.1%] | 811/845 = 96.0% [94.4%, 97.1%] |
| unsupported | 238 | 220/238 = 92.4% [88.4%, 95.2%] | 47/238 = 19.7% [15.2%, 25.3%] |

## Single-family tasks only

| family | n | passed | kept |
|---|---|---|---|
| F1 | 225 | 224/225 = 99.6% [97.5%, 99.9%] | 224/225 = 99.6% [97.5%, 99.9%] |
| F2 | 129 | 129/129 = 100.0% [97.1%, 100.0%] | 129/129 = 100.0% [97.1%, 100.0%] |
| F3 | 59 | 39/59 = 66.1% [53.4%, 76.9%] | 39/59 = 66.1% [53.4%, 76.9%] |
| F4 | 119 | 119/119 = 100.0% [96.9%, 100.0%] | 119/119 = 100.0% [96.9%, 100.0%] |
| F5 | 149 | 148/149 = 99.3% [96.3%, 99.9%] | 148/149 = 99.3% [96.3%, 99.9%] |
| F6 | 100 | 89/100 = 89.0% [81.4%, 93.7%] | 89/100 = 89.0% [81.4%, 93.7%] |
| F7 | 93 | 93/93 = 100.0% [96.0%, 100.0%] | 93/93 = 100.0% [96.0%, 100.0%] |
| F8 | 102 | 102/102 = 100.0% [96.4%, 100.0%] | 102/102 = 100.0% [96.4%, 100.0%] |
| F9 | 73 | 70/73 = 95.9% [88.6%, 98.6%] | 70/73 = 95.9% [88.6%, 98.6%] |
| F10 | 96 | 96/96 = 100.0% [96.2%, 100.0%] | 96/96 = 100.0% [96.2%, 100.0%] |
| F11 | 95 | 93/95 = 97.9% [92.6%, 99.4%] | 93/95 = 97.9% [92.6%, 99.4%] |
| F12 | 127 | 127/127 = 100.0% [97.1%, 100.0%] | 127/127 = 100.0% [97.1%, 100.0%] |
| unsupported | 238 | 220/238 = 92.4% [88.4%, 95.2%] | 47/238 = 19.7% [15.2%, 25.3%] |

## By number of families

| families in the task | n | kept |
|---|---|---|
| 0 | 238 | 47/238 = 19.7% [15.2%, 25.3%] |
| 1 | 1367 | 1329/1367 = 97.2% [96.2%, 98.0%] |
| 2 | 1142 | 1107/1142 = 96.9% [95.8%, 97.8%] |
| 3 | 608 | 592/608 = 97.4% [95.8%, 98.4%] |
| 4 | 135 | 124/135 = 91.9% [86.0%, 95.4%] |

## Unsupported tasks per category, after filtering (top-up from the oracle when kept < 20)

| intent | n | passed | kept |
|---|---|---|---|
| unsup.voice | 18 | 18/18 = 100.0% [82.4%, 100.0%] | 1/18 = 5.6% [1.0%, 25.8%] |
| unsup.upscale | 27 | 16/27 = 59.3% [40.7%, 75.5%] | 11/27 = 40.7% [24.5%, 59.3%] |
| unsup.stabilize | 30 | 26/30 = 86.7% [70.3%, 94.7%] | 2/30 = 6.7% [1.8%, 21.3%] |
| unsup.subtitles | 26 | 26/26 = 100.0% [87.1%, 100.0%] | 11/26 = 42.3% [25.5%, 61.1%] |
| unsup.background | 29 | 27/29 = 93.1% [78.0%, 98.1%] | 1/29 = 3.4% [0.6%, 17.2%] |
| unsup.blur_faces | 30 | 30/30 = 100.0% [88.6%, 100.0%] | 1/30 = 3.3% [0.6%, 16.7%] |
| unsup.transcribe | 30 | 29/30 = 96.7% [83.3%, 99.4%] | 19/30 = 63.3% [45.5%, 78.1%] |
| unsup.colour_grade | 24 | 24/24 = 100.0% [86.2%, 100.0%] | 1/24 = 4.2% [0.7%, 20.2%] |
| unsup.remove_object | 24 | 24/24 = 100.0% [86.2%, 100.0%] | 0/24 = 0.0% [0.0%, 13.8%] |

### What the teacher put in `nearest_supported` on passed unsupported tasks

| intent | teacher's label | accepted |
|---|---|---|
| unsup.background | F3 | **no (filtered)** | 3
| unsup.background | F4 | **no (filtered)** | 23
| unsup.background | None | yes | 1
| unsup.blur_faces | F4 | **no (filtered)** | 29
| unsup.blur_faces | None | yes | 1
| unsup.colour_grade | F3 | **no (filtered)** | 23
| unsup.colour_grade | None | yes | 1
| unsup.remove_object | F1 | **no (filtered)** | 1
| unsup.remove_object | F4 | **no (filtered)** | 23
| unsup.stabilize | F12 | **no (filtered)** | 3
| unsup.stabilize | F3 | **no (filtered)** | 7
| unsup.stabilize | F4 | **no (filtered)** | 12
| unsup.stabilize | F5 | **no (filtered)** | 2
| unsup.stabilize | None | yes | 2
| unsup.subtitles | F10 | **no (filtered)** | 2
| unsup.subtitles | F3 | **no (filtered)** | 8
| unsup.subtitles | F9 | **no (filtered)** | 5
| unsup.subtitles | None | yes | 11
| unsup.transcribe | F7 | **no (filtered)** | 10
| unsup.transcribe | F9 | yes | 19
| unsup.upscale | F3 | **no (filtered)** | 5
| unsup.upscale | F4 | yes | 11
| unsup.voice | F10 | **no (filtered)** | 8
| unsup.voice | F12 | **no (filtered)** | 1
| unsup.voice | F9 | **no (filtered)** | 8
| unsup.voice | None | yes | 1

## Ambiguous tasks per category

| intent | n | kept |
|---|---|---|
| amb.fix | 9 | 8/9 = 88.9% [56.5%, 98.0%] |
| amb.trim | 27 | 27/27 = 100.0% [87.5%, 100.0%] |
| amb.audio | 18 | 18/18 = 100.0% [82.4%, 100.0%] |
| amb.convert | 35 | 16/35 = 45.7% [30.5%, 61.8%] |
| amb.shorter | 22 | 22/22 = 100.0% [85.1%, 100.0%] |
| amb.smaller | 38 | 27/38 = 71.1% [55.2%, 83.0%] |

