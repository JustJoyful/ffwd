# Independent security and privacy review of ffwd-web (`main`)

Scope: `/home/joydeep/Projects/ffwd-web`, branch `main`, read-only. I read `app/`, `public/_headers`, `vite.config.js`,
`isolation-headers.js`, `react-router.config.js`, `scripts/`, the protocol schemas and allow-list, the built output in
`build/client` (to check what actually ships), and the relevant parts of `node_modules/@wllama/wllama` (its cache and
download code decides what the integrity check really protects). I ran one check: a copy of `app/agent/validator.js` under
plain `node` (finding S1). I did not start a browser, run vitest, or read any history or notes folders.

Verdict in one paragraph: the privacy design is sound and the analytics wrapper is better than most. Claims 1, 2, 5 and 8 hold.
Claims 3, 4 and 6 hold with caveats listed below. Claim 7 (validator cannot be bypassed) is **false** as written: there is a
reproducible filtergraph bypass. Two launch-blocking deployment problems (B1, B2) are not about the model or privacy but would
make the public site not work as built.

---

## Findings

### B1 (blocker, verify on a Pages preview) `/app` has no HTML file on Cloudflare Pages

- `react-router.config.js:6-15`: `ssr: false`, `prerender` is `/`, `/privacy`, `/requirements`, `/chores…`, `/404`. `/app` is absent.
- `build/client` contains `404/`, `404.html`, `chores/`, `privacy/`, `requirements/`, `index.html`, `__spa-fallback.html`. There is no
  `app/` folder and no `_redirects` file in `public/` or `build/client`.
- `scripts/postbuild.mjs:12` copies the prerendered 404 page to `404.html`. Cloudflare Pages treats a top-level `404.html` as "this is
  not an SPA" and answers unknown paths with that file and status 404 instead of falling back to `index.html`.
- Every entry to the tool is a full document load of `/app` by design: `[data-choose]` anchors are plain `href="/app"`
  (`tests/build/home-content.test.js:64`), `showcase.js:379` does `location.assign("/app")`, chore pages link `/app?ask=`.
- Scenario: a visitor clicks "Choose a video" on the home page and gets the 404 page's HTML (status 404), with whatever hydration
  recovery React Router manages, or the not-found page. The e2e suite runs the dev server (`playwright.config.js` comment says a
  static server would answer `/app` with the home page), so nothing tests this.
- Fix (smallest): add `"/app"` to `prerender` (the route has a `clientLoader` and a `HydrateFallback`, so it prerenders the fallback), or add
  `public/_redirects` with `/app /__spa-fallback.html 200`. Then confirm with `wrangler pages dev build/client` that
  `curl -I /app` is 200 and has COOP/COEP.

### B2 (blocker, known but ungated) The ffmpeg core cannot be deployed as built

- `public/_headers:27-31` says it: `ffmpeg-core.wasm` is 32,718,323 bytes (`build/client/ffmpeg/`), Pages caps a file at 25 MiB.
- `.gitignore` ignores `public/ffmpeg/`; `package.json` `build` is `react-router build && node scripts/postbuild.mjs`, which does not run
  `copy-core`. A clean CI build therefore has no `/ffmpeg/*` at all. `FFMPEG_CORE_BASE = "/ffmpeg"` is hard-coded
  (`app/agent/config.js:30`).
- Scenario: deployed from a clean checkout, `toBlobURL("/ffmpeg/ffmpeg-core.js")` (`ffmpeg-session.js:42`) fetches the 404 page. `toBlobURL` does
  not check `response.ok` (`@ffmpeg/util` index.js:147-152), the core fails to start, and the person is told their video is broken (see S4).
- Fix: decide the asset host now (R2 as planned), make `FFMPEG_CORE_BASE` a build-time config value, and make `check-release` fail when it
  is still `/ffmpeg` or when any file in `build/client` is over 25 MiB.

### S1 (should-fix, high) Allow-list filtergraph validator is bypassable: quote handling differs from FFmpeg's

Evidence, `app/agent/validator.js:59-67` (`splitGraph`):
```js
if (ch === "\\" && i + 1 < graph.length) { buf += graph.slice(i, i + 2); i++; continue; }   // escape honoured everywhere
if (ch === "'") quoted = !quoted;
```
FFmpeg's `av_get_token` (used for filter args, libavutil/avstring.c) honours `\` only OUTSIDE single quotes; inside quotes a backslash is a
literal and the next `'` closes the quote. So `'\'` is a complete quoted string to FFmpeg but "opens a quote and escapes a quote" to the validator.
(The FFmpeg side is from my knowledge of its source, not from running FFmpeg; the validator side is a real run.)

Reproduction (I ran a copy of `validator.js` under node; real result, not inferred):
```
["-i","{in:a}","-filter_complex","null='\\',movie=in_0.mp4'","{out:o}"]   -> {"ok":true}
["-i","{in:a}","-vf","movie=in_0.mp4","{out:o}"]                          -> rejected "filter not allowed: movie"
["-i","{in:a}","-vf","null='\\',amovie=x:y=1'","{out:o}"]                 -> {"ok":true}
```
The validator sees one part, `null`, with a quoted argument, and the checks `FILTER_NAME`, `allowlist.filters` and `PROTOCOL_OR_PATH` (line 33,
only `x:/` and `..`) pass. FFmpeg sees `null=\` then `,` then a second filter `movie=in_0.mp4'`, i.e. a filter that is not on the allow-list and
that opens files. No brackets are needed, so the label rules are not hit.

Impact: the allow-list guarantee ("filters that read files are deliberately absent", `allowlist.json` `_doc`) does not hold. In the browser the reach is
bounded by the ffmpeg.wasm in-memory file system (it can read the person's own input and earlier outputs, and run any filter compiled into the core:
`movie`, `amovie`, `sendcmd`, `drawtext` and others). It is not a path to the real disk or the network, so I rate it should-fix, not blocker. The
Python validator is documented as a twin kept in step by `protocol/conformance/validator.jsonl`, so the same bug is very likely in training and in
the native CLI, where the reach is the real file system. I did not read the Python twin.

Fix: in `splitGraph`, only treat `\` as an escape when not inside quotes (match `av_get_token`). Even simpler and stricter: reject any `'` or `\` in
`-vf/-af/-filter_complex` values if no trained task needs them (check first: `select='gt(scene,0.4)'`-style tasks may exist; if so implement the
`av_get_token` rule exactly). Add the three cases above to the conformance suite on both sides.

### S2 (should-fix) The "verified" marker is a field wllama itself fills from the host's claim; verify-then-reload is by URL

- `model-host.js:80`: `if (size === msg.bytes && meta?.sha256 === msg.sha256) return true;` skips the hash. Same trust in `client.js:42` (`defaultIsCached`).
- The field it trusts, `metadata.sha256`, is also written by wllama's own `download()` (`node_modules/@wllama/wllama/src/cache-manager.ts:154,412`):
  for any URL containing `/resolve/` it fetches `…/raw/…`, parses `oid sha256:<hex>` and stores it as `metadata.sha256` after the download finishes
  (`huggingface.ts:138-151`). The planned primary host is Hugging Face, so this applies.
- Scenario: the tab is closed, crashes, or runs out of memory during the JS hash of the 444 MB file (`model-host.js:110`, a pure-JS sha256) after
  `download()` returned. The file is on disk, the marker already equals the pinned value because the host said so, and the next visit takes the warm path at line 80 and loads
  bytes that were never hashed. With an honest host this loads a correct file; with a compromised repo (the exact case the pin is for) it loads whatever the host served.
  It needs a compromised host plus an interrupted first load, so the practical risk is low, but the design promise ("verified before use") is not what the code guarantees.
- Related: after the hash passes, the file is loaded with `w.loadModelFromUrl(msg.modelUrl)` (`model-host.js:122`), which goes back through wllama's cache lookup and
  can call `download()` again if its own metadata checks fail, so the loaded bytes are not guaranteed to be the bytes that were hashed.
- Fix: do not reuse the field. After a successful hash write your own key (`ffwdVerifiedSha256`) and test only that in both places. Load the verified blob
  (`w.loadModel([blob])`) instead of `loadModelFromUrl`.

### S3 (should-fix, high) The plan the person confirms hides three fields that decide whether a check passes

- The model writes the spec. `chips.js` (what is shown) never mentions `time.tolerance_s`, `quality.min_ssim`, `quality.min_psnr_db` values (only the words
  "close to the original"), `per_input`, or the second output's content. `describe-spec.js:96` does `delete t.tolerance_s` on purpose.
- Schema: all three are unbounded `number|null` (`spec.schema.json` `num`).
- Scenario: a run fails the duration check; the model re-emits `spec` with `tolerance_s: 60` (the loop allows it, `machine.js` `case "spec"`). The person sees the same chips
  ("Keep 0:05 to 0:10"), presses Run, the same bad output now passes, and the page says "Done, every check passed" (`app.jsx:325`). The statement is true of the spec on the
  machine and false of what the person agreed to.
- Fix: bound the three fields in `spec.schema.json` (for example `tolerance_s <= 1`, `min_ssim >= 0.5`, `min_psnr_db >= 20`), and refuse in the machine a
  re-proposed spec that loosens any numeric tolerance relative to the confirmed one; show tolerance and quality floors in the chips.

### S4 (should-fix) A broken engine is reported as "This video can't be read"

- `machine.js:279`: any exception from `deps.probeFile` becomes `set({name:"ready", error})`; `app.jsx:207`: `unreadable = name === "ready" && Boolean(state.error)`; the UI text
  is `UNREADABLE_TEXT` ("It may be damaged…", `ProbeReadout.jsx:13`).
- Core 404 (B2), a worker that fails to start, or out-of-memory while loading the 31 MB core all land there. The failure is honest in that nothing succeeds, but it blames the video.
- Fix: have `probeFile` distinguish "the engine did not start" (a typed error from `FfmpegSession.#ready`) from "ffmpeg could not parse the file", and show a separate notice for the first.

### S5 (should-fix) No Content-Security-Policy; the privacy promise is not browser-enforced

- `public/_headers` sends COOP, COEP, `nosniff`, `Referrer-Policy` only. No CSP, no `Permissions-Policy`, no `frame-ancestors`.
- A `connect-src` limited to `'self'`, the model host and the PostHog host would make "nothing else leaves the page" true by construction instead of by review.
  Adding only `connect-src … ; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'` (no `script-src`) does not interfere with the inline head script,
  React Router's inline context script, or ajv's `new Function` (`protocol/validate.js:2` notes it). `frame-ancestors 'none'` also stops another site framing `/app` to click "Download model".
- Caveat: the model host is not decided, so this has to be written when the host is.

### S6 (should-fix) Privacy page and consent gaps relative to what the code does

- The page says nothing else is sent ("Nothing else is sent", "The only requests to the counting service…"). The first model download sends an HTTP request to the model host
  (planned: Hugging Face) that carries the visitor's IP and user agent, and for an HF `/resolve/` URL wllama makes a second request to `/raw/` (`huggingface.ts:138`). Name the host and say so.
- The path cache stores a device description in `localStorage` for 30 days: key `ffwd:path:v1:<sha>:<vendor>|<architecture>|<description>` plus measured speeds (`path-cache.js:17-23`). It is never sent, but the
  "ID in your browser" section (`privacy.jsx:195-225`) lists only the PostHog ID. Disclose it.
- `ANALYTICS_PERSISTENCE = "localStorage"` with `ANALYTICS_IDLE_MS = 3000` writes a persistent random id and loads PostHog 3 s after page load with no banner and no opt-out other than DNT/GPC
  (`config.js:9-20`, `analytics.js:176-188`). `config.js` already flags this as an open owner question. For EU visitors the id in local storage is the exposure; either set `"memory"` or add a one-click
  opt-out. This applies only if a PostHog key is set at build; with no key nothing happens.
- Two `[Confirm …]` placeholders on the page are gated by `check-release.mjs`; keep that gate. Note `ip: false` makes PostHog send `?ip=0`, but the server still receives the TCP connection; "never collects your IP" is true
  only if the project setting "discard client IP" is also on, as the placeholder says.

### S7 (should-fix, low) Analytics allow-list: free-text strings of up to 40 characters pass on seven keys; `$process_person_profile` is stripped

- `analytics.js:86`: any string of 40 characters or fewer is accepted for `landing_page`, `referrer_domain`, `model_version`, `ms`, `input_size_bucket`, `n_files_bucket`, `seconds_bucket`. 40 characters is the length of a
  typical request or file name ("trim the first 10 seconds of holiday.mp4" is 39). Today every call site passes a bucket word or a fixed constant, so nothing leaks; the control is the call sites, not the wrapper.
  The unit test `analytics.test.js:167` pins "40 is sent". Fix: give each of those keys an enum (the bucket vocabularies already exist in `lib/buckets.js`, `MODEL.version`, the route names).
- `guardEvent` keeps only `token` and `distinct_id` (`analytics.js:50`). posthog-js sets `$process_person_profile` (false for `person_profiles: "identified_only"`) as an event property (checked in the built `module.slim` chunk), so the guard
  removes it and PostHog's server will create a person profile for every anonymous id. That is not a leak, but it is more than "anonymous counts" and costs more. Add `$process_person_profile` to `TRANSPORT_KEYS` (boolean only).

### S8 (should-fix, perf not safety) Two unparsable replies in a row demote a healthy GPU to the processor for 30 days

- `client.js:371-378` and `store.js:75` (`isValidReply = !("error" in parseAction(reply))`). A reply cut at the 512-token cap, or any malformed JSON from a good model, counts. Two in a row on a correct NVIDIA path call `switchToCpu`, which writes
  `webgpu: "broken", why: "replies"` (`client.js:295`) with the 30-day TTL (`config.js` `cacheTtlDays`). The model passes 867/900 in the project's own numbers, so two consecutive malformed turns do happen.
  Scenario: one unlucky job on a fast GPU, then about 3.7x slower steps (1.6 s vs 5.9 s measured, `capability.js` `MODEL_TURN_SECONDS`) for a month.
- Fix: do not persist the verdict for `why: "replies"` (switch for this page only), or require the same device to see it on two separate jobs, or exclude `finishReason === "length"` replies.

### S9 (should-fix) `check-release` does not gate the things that decide whether production works

`scripts/check-release.mjs` only greps for placeholder strings. Add: `VITE_MODEL_URL` was set at build time, is `https:`, and is not `localhost`; `VITE_POSTHOG_KEY` is set only on purpose; the build was not made
with `VITE_SCRIPTED_POLICY=1` (the built `app-main` currently has `gs=()=>!1`, i.e. off, which is right, but nothing enforces it, and the scripted branch also takes `globalThis.__ffwdScript` and
`__ffwdAnalytics` from the page); no file over 25 MiB (B2). Related: with no model URL the client sets `load_failed` with the "not published yet" message (`client.js:25`) but `ModelLoader`
prints the generic `MODEL_ERROR_TEXT.load_failed` and a "Try again" button (`ModelLoader.jsx` `failed` branch), so the honest message is never shown and Try again just repeats.

### S10 (should-fix, UX honesty) "Done, every check passed" can appear with nothing to download, and a save failure is silent

- Output handle is read as `passing.outputs.out1` (`app.jsx:178`). An `image_sequence` output (a directory) or a spec whose output id is not `out1` leaves `result` empty, the page says
  "Done, every check passed" and then "This result can't be saved as one file yet" / "Getting the file ready" with a disabled button. Download is correctly disabled and the failure is honest, but the
  headline is not. Show "Done" only when a blob exists, otherwise say the checks passed but the file cannot be saved yet.
- `DownloadButton.jsx:15`: `setDone(await saveFile(...))` has no catch. If `URL.createObjectURL` or the picker throws something other than `AbortError` and the fallback also throws, there is an unhandled rejection and no message.
  The `<a download>` fallback returns `true` ("Downloaded") even if the browser blocked it; that cannot be detected, so say "Download started" rather than "Downloaded".

### Nits

- N1 `model-host.js:82-85`: a cached file of the wrong size whose metadata `originalURL/originalSize` match is returned early by `download()` (`cache-manager.ts` "the file is reused") without a fetch; the host then hashes, fails, deletes, and the first
  attempt after a model update reports `hash_mismatch` although nothing was tampered with. Delete a wrong-sized entry before downloading.
- N2 `path-cache.js:46`: `now() - v.at` is negative for a future `at`, so a clock jump or hand-edited entry never expires. Reject `v.at > now() + DAY_MS`.
- N3 `model-host.js` canary and benchmark have no timeout. A WebGPU driver that hangs rather than throws leaves the first visit on "Starting the model" forever. Same for `generate`.
- N4 `browser-executor.js` `extensionOf(spec)`: the model's `container` (pattern `^[A-Za-z0-9_.+-]{1,32}$`) becomes the output extension, so FFmpeg picks a muxer from it and the `-f` muxer allow-list does not apply (e.g. `m3u8`, `mpd`).
  Bounded to the in-memory file system. Restrict `container` to the muxer allow-list.
- N5 `vite.config.js`: dev and `vite preview` send COOP/COEP only; `nosniff` and `Referrer-Policy` come only from `_headers`. With a PostHog key set in preview, the full `/app?ask=…` URL would be the Referer. Share the same two headers via `isolation-headers.js`.

---

## Every network call site in `app/` and `public/`

There is no `fetch(`, `XMLHttpRequest`, `sendBeacon`, `WebSocket`, `EventSource`, `importScripts` or service worker in `app/` (searched). The sites are all library-mediated:

| # | Where | Target | What it sends |
|---|---|---|---|
| 1 | Page load, `build/client` assets | same origin: HTML, `/assets/*`, `/media/*`, fonts (`@fontsource`, bundled) | normal page/asset requests; no video, name or text |
| 2 | `ffmpeg-session.js:42-47` via `toBlobURL` | same origin `/ffmpeg/ffmpeg-core.{js,wasm,worker.js}` | plain GETs |
| 3 | `model.worker.js:12,18` and wllama inner worker | same origin wasm asset; inner worker is a blob | plain GET |
| 4 | `model-host.js:85` `cm.download(url)` (wllama `cache-manager.ts` `download`) | `VITE_MODEL_URL` host (planned: Hugging Face) | GET with `Range`, possibly `HEAD`, and for `/resolve/` URLs a GET of `/raw/` (`huggingface.ts:145`). Request line plus normal browser headers (IP, UA, `Referer` = origin only). No prompt, no file, no adapter |
| 5 | `model-host.js:122` `loadModelFromUrl` | same host, only if wllama decides to re-download (S2) | as 4 |
| 6 | `analytics.js:134` `import("posthog-js/dist/module.slim.js")` | same-origin chunk | none |
| 7 | PostHog `init` in `analytics.js:136-151`, only when `VITE_POSTHOG_KEY` is set, not DNT/GPC, after first input or 3 s | `VITE_POSTHOG_HOST` | batches of events after `guardEvent`: `token`, `distinct_id`, the listed keys, `?ip=0`. posthog-js may also request its remote config (`/array/<token>/…`, string present in the chunk); that carries only the token. Flags, surveys, replay, external scripts are switched off |
| 8 | `<a href>` in `home.jsx:603,605`, `Shell.jsx:54,56` | opencontent.netflix.com, creativecommons.org | user navigation only; `Referer` is origin only |
| 9 | Built wllama code contains `cdn.jsdelivr.net/.../wllama-compat` | not used: `Wllama.compat` is `null` unless `setCompat` is called, and the app never calls it (`wllama.ts:358,434,1941`) | nothing |

No `console.*` is shipped anywhere (the only one in the app is `machine.js:105` `console.error` for a throwing subscriber, local); there is no error reporter (searched for sentry, bugsnag, datadog, gtag, window `error` handlers). Page title is static (`root.jsx` `meta`), no `document.title` assignment, no `history`/URL writes of any request text; `location.search`
is read only for `ask` (prefill, capped at 300 chars, `app.jsx:119`) and `theme`/`font` (cosmetic, `root.jsx:9`).

---

## Claims verified true (and what I checked)

**1. "Your videos never leave your computer": TRUE in code.** A chosen `File` goes `file.arrayBuffer()` then `session.write` (`browser-runtime.js:49-62`) into the wasm memory, plus a `blob:` URL for the viewer (`app.jsx:130`). Nothing in the call-site table above takes a file,
a name or bytes. File names reach only React text, the in-memory path (sanitised `safeName`, `browser-runtime.js:12`) and the download name. The model gets ids and a normalised probe built from fixed fields (`probe-log.js:44-110`, `probe.schema.json`), not names or metadata text.
The one caveat is the model download request itself (S6). Not verified in a browser.

**2. Text privacy: TRUE, with S7 as the weak spot.** `track` then `sanitize` then PostHog `before_send: guardEvent` (`analytics.js:62-107, 148`). Verified: unknown events dropped (`Object.hasOwn`), unlisted keys dropped, nested objects/arrays/null dropped
(only boolean, finite number, 40-character-or-shorter string, and `families` as F1..F12 or "other" pass), six keys are closed enums with "other" as the overflow (`ENUMS`), `category` is an always-empty enum so it is always "other". `guardEvent` builds a fresh object,
so `$set`, `$set_once`, `$current_url`, `$session_id`, `$device_id` and the rest of what posthog-js adds are removed (I confirmed in the built chunk that `before_send` runs on the full event). Callers (`analytics-bridge.js`) read only state names, counts, buckets and
`s.path`/`s.canary`; adapter data never enters it (`client.js` never reads `m.adapter`; grep finds no analytics use). The model's reply, ffmpeg args and logs, and file names are never passed to `track`. Disabled by default: `analyticsSettings().key` is `""` in the built
`config` chunk (`config-*.js`), `root.jsx:57` returns before importing anything, and PostHog is a dynamic import inside `load()` after first input or idle (`analytics.js:134,176-188`); DNT/GPC stops it entirely. Referrer reduced to hostname and own-host
dropped (`analytics-bridge.js:131-149`); `Referrer-Policy: strict-origin-when-cross-origin` is in `_headers`, so a request to PostHog carries the origin only, not `/app?ask=…`. Test coverage is real: `analytics.test.js`, `analytics-bridge.test.js` and
`tests/e2e/analytics.spec.js` (secret `?ask=` text, stubbed host, its own copy of the allow-list). They do not assert "no other third-party host was contacted" (`app-driver.js:49` records requests but only `flow.spec.js:148` filters foreign ones).

**3. Headers: TRUE for COOP/COEP, and it fails closed.** `public/_headers:10-14`: `/*` gets COOP `same-origin` and COEP `credentialless`, so every document, worker script and asset has them; `tests/build/shell.test.js:57` asserts the `/*` block equals `isolation-headers.js`. `vite.config.js:6-21` applies the same pair to the dev server (via middleware, because
`server.headers` misses the React Router document) and `preview.headers`. Missing headers: `checkCapability` returns `no-isolation` when `crossOriginIsolated !== true` (`capability.js`), the tool then renders only `CapabilityNotice` and no file input. The text says "Open it in Chrome, Edge or Firefox",
which is wrong advice if the cause is a host misconfiguration, but nothing half-works. No cross-origin sub-resource is loaded by pages (fonts and media are local; external links are navigations), so nothing is blocked by `credentialless`. The cross-origin ranged model fetch is a CORS `fetch` and needs no CORP;
`_headers:36-46` records it was verified on a stand-in file, not on our repo (not re-checkable here). Missing: CSP (S5). Pages `_headers` applies to static responses only, which is all this site serves.

**4. Model integrity: TRUE for a fresh download; weaker on the warm path (S2).** `ensureFile` (`model-host.js:75-121`): after any download it requires `blob.size === bytes` and the streaming sha256 equal to the pinned value (`config.js:5-6`); on mismatch it `cm.delete(name)` and throws `hash_mismatch` (lines 104-111), `init`'s catch frees the engine,
nothing is loaded. A size-only match is not enough (line 80 needs both size and marker); a redirect, a resume (wllama resumes only with a matching strong ETag and range), or a different file under the same name all end at the full hash at line 110 before first use. Pinned values: `MODEL.sha256`, `MODEL.bytes` are constants (`config.js`),
`validateWorkerMessage` requires 64 hex characters; the URL is `import.meta.env.VITE_MODEL_URL` only, set at build time. No `location.search`, hash, cookie or storage value can change either (the only `searchParams` use is `ask`). The cache key is `sha1(url)_filename`, so a different URL cannot reuse the file. Caveats: S2 (marker provenance, verify-then-reload by URL) and N1.

**5. Consent: TRUE.** `client.begin()` runs only after the first `fileChosen` (`store.js:84-93`). `start()` (`client.js`): a verified cache entry gives `launch(true)` without a prompt; otherwise `needsConsent` and nothing is fetched until `consent()`. `decline()` only sets a flag and `untilReady` rejects with `aborted`, so no job starts
(`canSubmit` is also blocked by `modelBlocks`). The 444 MB size shown is `MODEL.bytes` (`ModelLoader.jsx`). No `<link rel=preload|prefetch>` for the model, no service worker, no `fetch` of the model before `launch()`. The only pre-consent work is the main-thread cache probe (`defaultIsCached`, a dynamic import of wllama and OPFS reads) and `requestAdapter`.
Retry after a failure does not ask again (documented); it requires a click.

**6. Failure paths never look like success: TRUE for the machine, with S3 and S10.** `done` is reached only from `executeRun` returning `passed` (all spec outputs present and every check ok, `loop.js`) or from `finish` when `job.lastPassed` (`machine.js` `case "finish"`). Check is called inside `executeRun` after every executed run; a rejected
or failed run records `passed:false`. Check errors, missing outputs and probe failures become `passed:false` (`checker/index.js`, `check()` try/catch and `result()`). Typed model errors end as `failed` with a fixed sentence (`MACHINE_REASON`), `context_full` gives "too long", unsupported device renders no tool at all, a run timeout returns `ok:false`.
`Download` is disabled until a blob exists. The headline "Done, every check passed" is only shown for `name === "done"`. `tests/unit/invariants.test.js` covers finish-after-fail, four rejected runs, fuzzed scripts. The gap is S3: "every check passed" is relative to a spec the model can loosen.

**7. Command safety: PARTIALLY TRUE; the allow-list can be bypassed by S1.** What holds: every model `run` passes `validateRun` twice (`loop.js` `executeRun`, `browser-executor.js:50-58`); argv is a list, never a shell string; `-i` must be `{in:<id>}` (`validator.js`, `walk`); outputs only as `{out:<id>}`; any option not in `allowlist.options` is rejected, which covers
`-attach`, `-dump_attachment`, `-protocol_whitelist`, `-f lavfi` (muxer list), `-i` with URLs, response-file `@x` (a positional that is not `{out:…}`), `-y`, `-filter_script`, `-stats_file`, `-passlogfile`; option names are lowercase ASCII only (`OPT` regex), so case and Unicode look-alikes
fail; filter names must be in a 30-name list and `[a-z0-9_]+`, so `movie=`, `amovie=`, `subtitles=`, `drawtext=` are rejected when written plainly (verified for `movie`); brackets are only allowed as outer labels with `[A-Za-z0-9_:]`; argument count and length come from the schema (64, 512). Real paths never reach the model: prompts are built from
`{id, probe}` (`loop.js` `initialMessages`), and the executor rewrites the ffmpeg log tail replacing paths with `{in:…}`/`{out:…}` (`browser-executor.js:99-107`). The invariants test checks the prompt text for paths. The exception is S1; N4 is a minor related gap.

**8. WebGPU canary / path cache: TRUE.** Adapter strings: used only to build the `localStorage` key (`path-cache.js:17-23`) and in the worker's `readAdapter` result; the worker's `ready.adapter` is not read by the client, and analytics receives only `model_path` and `canary` words
(`analytics-bridge.js:45-54`, enum-guarded in `analytics.js:60-66`). Corrupt or hostile storage: `readVerdict` wraps everything in try/catch and checks shape, enum values, finite numbers, `path:"webgpu"` requires `webgpu:"ok"` and `canary:"pass"`,
`__proto__` or unexpected keys in `bench` fail the `Object.entries` test (`path-cache.js:35-56`); a failed read is "no verdict" and the page works; a failed write is ignored. A forged "webgpu ok" verdict can only skip the canary on the visitor's own browser, and the safety net then still applies. The fallback is bounded:
`invalidRun` resets per job and on any valid reply, `switchToCpu` runs once (`switched = true`; after it `state.path !== "webgpu"` so the check is off), the same step is re-asked exactly once (`client.js:371-381`), and a CPU load failure rejects the policy and ends the job (`untilReady`). The canary and benchmark failing counts as "broken" and
falls back to the processor (`model-host.js` probe branch). Residual: S8, N2, N3.

---

## Not checked

- Nothing was run in a browser. All behaviour of Cloudflare Pages (the `404.html` rule behind B1, `_headers` merging), Hugging Face (CORS, redirects, the `/raw/` pointer), and PostHog's server side (IP discard, person profiles, config endpoint) is from documentation, comments in the repo, and the shipped client code, not observed.
- The Python validator twin and `protocol/conformance/*.jsonl` (S1 is shown only for the JavaScript copy). The FFmpeg side of S1 (how `av_get_token` treats `\` inside quotes) is from my knowledge of its source; I did not run FFmpeg on the payload.
- Whether `public/ffmpeg/ffmpeg-core.*` is byte-identical to `@ffmpeg/core-mt@0.12.10` (it is copied by `copy-core.mjs`; I did not hash it), and what filters are compiled into that core (decides how much S1 gives an attacker).
- The Cross-Origin-Storage backend in wllama (`storage/cos.ts`), which is only active in browsers with that experimental API.
- `RunLog`, `CommandReveal`, `AskUser`, `Viewer`, `DropOverlay`, `PlanCard` for accessibility details beyond the consent and failure components (`ModelLoader` uses `role="status"`/`"alert"` and a labelled progressbar, which is fine); the marketing pages and `showcase.js`.
- Dependency supply chain (`pnpm-lock.yaml`, posthog-js, wllama) and the CI workflows beyond a read of `ci.yml`.
- I did not run the vitest or Playwright suites; I relied on reading them.
