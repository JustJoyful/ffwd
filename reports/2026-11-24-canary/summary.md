# WebGPU canary and path choice: evidence (24 Nov 2026)

Code: branch `stream-B2` of `ffwd-web` (worktree `../ffwd-web-B2`, not merged, not pushed). Nothing public, no spend, no model-repo preregistration, checker or metric change. Every browser run was under `systemd-run --user --scope -p MemoryMax=5G -p MemorySwapMax=0` with Chromium started without the user D-Bus variables, one browser job at a time; the smoke script refuses to start without a cap and has a 2 GB low-memory watchdog (lowest available RAM seen in the three final runs: 5.0 GB).

## The canary

- Prompt: the whole system prompt (1333 tokens) plus a first user turn, rendered with the agent chat template, greedy, 20 new tokens. It is stored in `app/model/canary-reference.json` (site repo) with the model sha256 `bbf439b7...`, the first 20 token ids and the text `{"action": "spec", "spec": {"family": ["F1"], "outputs": [{"`, made by `scripts/make-canary-reference.mjs` from native llama.cpp b12032-dde879bc4 (CPU, f16 KV, no flash attention; the browser uses q8_0 KV + flash attention and still matched 20 of 20). Every one of the 20 greedy steps has a log-probability gap of at least 4.3 between the best and second-best token.
- Why the whole system prompt and not a short one: my first, shorter canary (774 tokens) PASSED on the Intel iGPU. The failure depends on prompt length. Bisected on the Intel adapter: 774 and 837 tokens correct; 881, 950, 1176 and 1333 wrong. A real job's first turn is about 1330 tokens, so the canary has to be as long as the real workload or it vouches for a path that fails the job. Data: `study/`.
- Match rule: pass needs 18 of the first 20 ids (`PATH_CHOICE.canaryMinMatch`).

| Configuration (same file, q8_0 KV + FA, ctx 8192) | matched, of 20 | first run | notes |
|---|---|---|---|
| NVIDIA RTX 3050 WebGPU, 1333 tokens | 20, 20 (two runs) | 4.6 s | prompt 312 tok/s, generation 56 tok/s |
| wllama CPU, 4 threads, 1333 tokens | 20, 20 | 20.5 s | prompt 67, generation 33 tok/s |
| Intel gen-12lp WebGPU, 1333 tokens | 0, 0, 0 (three runs, each repeated once, still 0) | 22 to 42 s | every reply a repeated garbage token |
| Intel, 774 / 837 / 881 / 950 / 1176 tokens | 20 / 20 / 0 / 0 / 0 | | the length bisection |

Why 18: correct paths scored 20 and every broken run scored 0, so any threshold from 1 to 20 separates the data. 18 rather than 20 leaves room for one or two late-token flips from another device's float behaviour (the margins make a flip very unlikely); 18 rather than something low keeps a half-broken path out. A wrong call costs speed (a good GPU run on the processor), never wrong output. Greedy decoding diverges after the first mismatch, so the rule is a prefix match, not a count of equal positions.

## Real runs (app, real model, real Chromium, scripts/app-smoke.mjs; `run-*/smoke.json` and key screenshots)

All three: the model asked before downloading, downloaded and was checked, the first-visit check ran, the request "Cut the first 2 seconds off" was planned and run, every check passed, the file saved, and a second visit loaded the remembered verdict in under 0.3 s with no check notice. The "this takes a while" notice was seen on screen (recorded inside the page: the browser's remote-control channel stalls during a WebGPU check, so polling from outside missed it at first); the page's main thread never stalled more than 120 ms (heartbeat).

| Run | Adapter the page saw (asserted) | Canary | Path chosen | Stored speed, prompt / generation tok/s | First check, wall | Job |
|---|---|---|---|---|---|---|
| (a) default | nvidia / ampere, not fallback | pass | WebGPU | WebGPU 395 / 60, CPU 78 / 50 | 17 s incl. download and hashing | done |
| (b) Intel-only Vulkan ICD | intel / gen-12lp, not fallback | fail (0 of 20) | processor | CPU 67 / 56 | 76 s incl. download | done on the processor |
| (c) no GPU flags | no adapter (requestAdapter() null) | skipped | processor | CPU 80 / 56 | 8 s | done |

- (a) WebGPU won the speed test: a typical step (200 prompt + 60 generated tokens) takes 1.5 s there against 3.8 s on the processor. The processor generates nearly as fast as the GPU (50 against 60 tok/s) but reads the prompt five times slower.
- (b) The app said: "A check on this computer found that its graphics chip gives wrong answers with the model, so ffwd uses your processor instead...". The page's adapter and the runtime's own log line were both Intel.
- (c) The wait estimate was shown as measured ("On this computer, the first step takes about 20 seconds and each step after it about 4 seconds"). The first step is long because a new page reads the whole 1333-token prompt; the old constants (10 s first step) assumed a cached prompt.
- Files: `run-nvidia/`, `run-intel/`, `run-cpu/`.

## Covered by unit tests only (no real run)

Runtime safety net (two unreadable replies in a row on the graphics path mark it broken, swap the worker for a processor one and redo the same step without the garbage); threads = min(4, max(1, floor(cores / 2))); memory under 4 GB refused, 4 up to but not including 8 runs with a warning, unreported gets none.

## Not done or not shown

- One machine only: this NVIDIA card and this one Intel iGPU.
- The safety net was not provoked in a real browser.
- The 30-day verdict lifetime is my addition (a driver update can win a device back).
- A graphics engine that fails to start or throws during the canary is treated as a failed canary and cached, so a one-off out-of-memory would pin that device to the processor for up to 30 days.
