# ffwd-web launch inventory (23 Nov 2026, night; read-only, by a subagent; main = 0c61afe)

"Verified" = the code was read or run; the rest is from commit messages or docs. The WEB_ARCHITECTURE.md and DESIGN.md files are partly stale (Tailwind, `tokens.css`, `app/workers/`, an Ink and Cobalt palette): the code is the truth.

## Launch items

| Item | Status | Files | Missing |
|---|---|---|---|
| ffmpeg worker (thread cap, concat deadlock) | done | `app/agent/executor/{ffmpeg-session,harness-args,browser-executor}.js`, `agent/config.js` (`-threads 4` per output, `-threads 1` per input, filter threads 1) | no own worker file (the library's worker is used); core is 32.7 MB, over Cloudflare Pages' 25 MiB per file, so production needs R2 with CORP |
| model worker, wllama, JS prompt renderer | partial | `app/agent/chat-template.js` (byte-identical, tested) | no worker, nothing imports wllama; `store.js` default policy throws "model not available" |
| model download consent, progress, OPFS cache | partial | `components/tool/ModelLoader.jsx` (4 states, not wired) | consent step, progress source, OPFS, sha256 check, model URL and version, `model_load_*` events, a loading state |
| capability check WebGPU vs CPU | done on `feat/cpu-path` (now merged into `integration`) | `lib/capability.js`, `ModelPathNotice.jsx`, machine `path`/`notice`, async `store.js`, requirements copy, bench kit | analytics bridge still sends `webgpu: Boolean(navigator.gpu)`; `shader-f16` and iGPU result pending |
| agent state machine and loop | done | `agent/{machine,loop,actions,scripted-policy,config}.js` (<=4 runs, check after every run, ask_user once, unsupported) | no model-loading state, no "too long" ending (`policy_error` only) |
| JS checker and probe | done | `agent/checker/*`, `agent/measure/*`, `numbers.js` | Python parity proven for offset and 5 wasm rotation cases only |
| allowlist and Ajv validators | done | `agent/validator.js` (39 conformance cases), `agent/protocol/validate.js` | Ajv compiles with `new Function`: blocks a strict CSP (none today) |
| conformance green in JS | partial | `tests/unit/conformance.test.js`: validator 39, describe-spec 8, checker-offset 8; e2e: offset + 5 rotation cases | `test.todo`: checker-frames 9, invariants 13, quality 6, rotation 12 (7 native-only) |
| /app UI in flow order | done, one piece unwired | `routes/app.jsx`: Video (ProbeReadout, FileIntake), request (RequestField), plan (AskUser, Unsupported, PlanCard), checks (RunLog, CheckList, RunProgress), save (DownloadButton, CommandReveal), Viewer, DropOverlay, StatusDot, CapabilityNotice | `ModelLoader` not wired; no sound module, no Bencho blocks, no polish/axe pass; FrameStrip, RangeBracket, HelperHandoff not built |
| home CTA to /app | done | `routes/home.jsx` (plain `<a href="/app">` so isolation headers apply) | GitHub and Research links are placeholders |
| privacy and requirements pages | done | `routes/privacy.jsx` (generated from `EVENTS`), `routes/requirements.jsx`, build tests | copy is for owner review |
| chore pages | done (5 + index) | `content/chores.js`, `routes/chore.jsx`, `routes/chores-index.jsx`; each pre-fills `/app?ask=` | DESIGN says about 20 at launch, PHASES says 5 |
| analytics wrapper | done, disabled by default | `lib/analytics.js` (allowlist per event, enums, 40-char cap, `before_send`), `tool/analytics-bridge.js`; DNT/GPC respected; forbidden-key unit test + e2e | `model_load_started/completed` defined but never sent; PostHog under COEP credentialless unverified |
| `_headers`, isolation, Cloudflare | partial | `public/_headers`, `isolation-headers.js` | no wrangler/Pages config, no R2 host, no model host config; `SITE_URL` placeholder blocks `check:release` |
| CI | done | `.github/workflows/ci.yml` (lint, unit, build tests; budgets), `protocol-drift.yml` | CI runs no Playwright e2e |
| home bundle size | over budget | `.size-limit.mjs` 120 kB gzip | last measured 123.49 kB; React + Router about 109 kB, site code under 15 kB; the limit must not be raised without the owner |
| test-real guard | done | `tests/unit/no-test-real.test.js` (scans app, tests, public) | does not scan `scripts/` or `spikes/` |

## Design system
Tokens are CSS custom properties in `app/styles/theme.css` (364 lines, ported from mockup-v5: dark, amber accent `#ffb224`, Funnel Sans and Funnel Display); `pages.css` (pages), `tool.css` (the /app, 461 lines), `fonts.css`. No Tailwind, no tokens.css. Components: `components/site/{Shell,ChoreDiagram}`, 16 under `components/tool/` (AskUser, CapabilityNotice, CheckList, CommandReveal, DownloadButton, DropOverlay, FileIntake, ModelLoader, PlanCard, ProbeReadout, RequestField, RunLog, RunProgress, StatusDot, Unsupported, Viewer) plus `ModelPathNotice`. Every flow step has a component; the model loader is the only unwired one.

## Tests (before the merge)
Unit 370 passed, 3 todo (main); 387 on `integration` (with the CPU path). Vitest projects: unit, build (needs a prior build), browser-gguf (opt-in). Playwright e2e: runtime (8), conformance (offset, rotation), flow (trim, size, iphone chores plus keyboard, non-video, unsupported, drop during a job), analytics (allowed events, DNT). Not run in this inventory.

## Risks
Headless Chromium has no WebGPU, so the real model cannot be tested in CI (scripted policy lane + a manual smoke test). Model hosting is blocked on a public HF repo (DeepSeek terms review). The marketing boundary (marketing files must not import `agent/` or `@ffmpeg/*`) is enforced by a unit test, not ESLint (the config edit is blocked by a hook). `EVENTS`, the privacy page and `analytics.test.js` must change together.
