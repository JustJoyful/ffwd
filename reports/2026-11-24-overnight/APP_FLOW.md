# /app flow: the two state machines (24 Nov 2026)

Source: `app/agent/machine.js` (the job), `app/model/contract.js` + `client.js` (the model), `app/lib/capability.js` (the device). The job machine knows nothing about downloading: the model client is a `Policy` (`messages -> Promise<string>`) that waits until the model is ready, so the job simply rests in `planning` while the model loads.

## 1. The job (what the person sees)

```
 checkingCapability --(device cannot run ffwd)--------------------------------------> unsupportedDevice   (reason: no-isolation | low-memory | mobile)
        |
        v  capability ok  (path: webgpu | cpu, notice: no-webgpu when on the processor)
      ready --(file chosen)--> probing --> awaitingRequest --(request sent)--> planning
                                  |                                              |
                          unreadable file                    +-------------------+--------------------+
                          (stays, error text)                |                   |                    |
                                                         askingUser        awaitingConfirm        unsupported
                                                        (ask once)         (plain-language plan)   (model says it cannot)
                                                             |                   |
                                                         answered        confirmed ("Run it")
                                                             |                   v
                                                          planning         running --> checking  (the harness checks after EVERY run)
                                                                              |            |
                                                                              |     check passed --> done ("Done, every check passed")
                                                                              |     check failed --> running again (<= 4 runs, <= 8 turns)
                                                                              v
                                                                           failed   (budget spent, invalid actions, model error)
 any resting state --(newRequest / new file)--> awaitingRequest   (path and notice are kept)
```

Rules the machine enforces: at most 4 runs and 8 turns; the check is run by the harness, never by the model; `finish` without a passing check is rejected; a second `ask_user` is fed back as invalid; the model never sees real paths (ffmpeg log tails reach it with `{in:id}`/`{out:id}`); a failed or too-long job is never shown as success.

## 2. How a model error ends a job
`policy` throws an Error with a `.code` -> job goes to `failed` with a plain sentence:

| code | reason | what the person reads |
|---|---|---|
| context_full | too_long | "This job got too long for the on-device model, so it was not done." |
| load_failed / hash_mismatch / out_of_memory / generate_failed | model_unavailable | the sentence for that code (reload, close tabs, try again) |
| aborted | aborted | "The job was stopped." |
| anything else | policy_error | the error detail |

## 3. The model (what the loader shows; `ModelState.phase`)

```
 idle --(first file chosen: store calls model.begin(path))-->  cached in this browser?
                                                                 |yes                           |no
                                                                 v                              v
                                                              loading                     needsConsent  ("Download 444 MB once?")  --Not now--> (declined: planning cannot start; Download again)
                                                                 |                              |Download
                                                                 |                              v
                                                                 |                         downloading (bytes, percent, saved for next time)
                                                                 |                              | verify sha256 (mismatch deletes the file)
                                                                 |<-----------------------------+
                                                                 v
                                                              ready  (path webgpu | cpu, loadMs, cached)
 any phase --(load or runtime error)--> failed (message; Try again unless out_of_memory)
```
No model URL in a build -> `failed` with "not published yet", never a fake download. A scripted build (tests) uses a stub that is always `ready`.

## 4. The device path
`navigator.gpu` present and `requestAdapter()` returns a real adapter (not a fallback, not SwiftShader/llvmpipe) -> **webgpu**; otherwise **cpu** with a notice and an honest wait (processor: first step about 11 s, later steps about 6 s, a typical job about 23 s of model time, measured on one laptop; slower computers take longer). Not refused: only no cross-origin isolation, a phone, or under 4 GB of reported memory.

## 5. Where the pieces live
`app/agent/` the job (machine, loop, checker, validators, executor over ffmpeg.wasm); `app/model/` the model (contract, host, worker, client, sha256, config); `app/tool/store.js` wires both for React (`useTool()` returns `{ state, dispatch, store, model, modelActions }`); `app/components/tool/` the UI; `app/lib/capability.js` the device check; `app/tool/analytics-bridge.js` the (disabled by default) analytics.
