Pass-rate table: K=8, band [0.2, 0.8], temperature 1.0, model `ffmpeg-agent-m1-0.6b (GGUF Q8_0, llama-server b12032, 4 slots)`, 302 tasks (seeded sample of 1000)

| group | n | in band | too easy (>80%) | too hard (<20%) | share in band [95% CI] |
|---|---|---|---|---|---|
| ALL | 302 | 9 | 285 | 8 | 3% [2%, 6%] |
| NOT in M1's SFT data | 8 | 0 | 6 | 2 | 0% [0%, 32%] |
| difficulty: 1 | 144 | 4 | 136 | 4 | 3% [1%, 7%] |
| difficulty: 2 | 96 | 1 | 93 | 2 | 1% [0%, 6%] |
| difficulty: 3 | 50 | 4 | 45 | 1 | 8% [3%, 19%] |
| difficulty: 4 | 12 | 0 | 11 | 1 | 0% [0%, 24%] |
| families: 1 | 104 | 4 | 96 | 4 | 4% [2%, 9%] |
| families: 2 | 96 | 1 | 93 | 2 | 1% [0%, 6%] |
| families: 3 | 50 | 4 | 45 | 1 | 8% [3%, 19%] |
| families: 4 | 12 | 0 | 11 | 1 | 0% [0%, 24%] |
| in M1's SFT data | 294 | 9 | 279 | 6 | 3% [2%, 6%] |
| involves F1 | 112 | 0 | 110 | 2 | 0% [0%, 3%] |
| involves F10 | 31 | 1 | 28 | 2 | 3% [1%, 16%] |
| involves F11 | 11 | 0 | 10 | 1 | 0% [0%, 26%] |
| involves F12 | 78 | 4 | 73 | 1 | 5% [2%, 12%] |
| involves F2 | 15 | 0 | 13 | 2 | 0% [0%, 20%] |
| involves F3 | 25 | 1 | 24 | 0 | 4% [1%, 20%] |
| involves F4 | 77 | 5 | 70 | 2 | 6% [3%, 14%] |
| involves F5 | 40 | 1 | 38 | 1 | 2% [0%, 13%] |
| involves F6 | 25 | 2 | 23 | 0 | 8% [2%, 25%] |
| involves F7 | 15 | 0 | 13 | 2 | 0% [0%, 20%] |
| involves F8 | 7 | 1 | 6 | 0 | 14% [3%, 51%] |
| involves F9 | 74 | 3 | 69 | 2 | 4% [1%, 11%] |
| kind: ambiguous | 16 | 0 | 16 | 0 | 0% [0%, 19%] |
| kind: unsupported | 24 | 0 | 24 | 0 | 0% [0%, 14%] |
