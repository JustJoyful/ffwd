# Overnight: the site on Cloudflare (night of 25 Nov 2026, times IST)

Live address: https://ffwd-web.joydeepdas217.workers.dev  (Worker `ffwd-web`, builds on every push to `main` of JustJoyful/ffwd-web)

## State at the end
- Live, correct headers (COOP same-origin, COEP credentialless, CSP, Referrer-Policy no-referrer), every page 200 with no redirect.
- **Full product flow verified on the live site with the real model** (`real-run/`): consent, 444 MB download from Hugging Face, sha256 check, graphics canary (pass, WebGPU 402/56 tok/s vs processor 78/55), a trim job whose checks passed, file saved, second visit 0.33 s from the stored verdict. 10 of 10 steps passed.
- Your portrait + volume request on the live site (`portrait-volume/`): "This plan doesn't change anything. Reword your request?", plus "Your request mentions a portrait picture, but this plan doesn't change it." and the same for the volume. No plain Run it. Nothing was run.

## What I changed (all pushed to ffwd-web main)
1. `wrangler.jsonc` so Cloudflare serves `build/client`; `html_handling: drop-trailing-slash` (no /app -> /app/ redirect).
2. Build variables set on the Worker's build trigger with the `cf` CLI (read back to confirm): VITE_MODEL_MANIFEST_URL (HF tag v1.0.0), VITE_MODEL_MANIFEST_SHA256 (90cc698e...), VITE_FFMPEG_CORE_BASE (jsDelivr), VITE_SITE_URL (the workers.dev address).
3. R2 is NOT enabled on the account (API error 10042, only you can enable it), so the 31 MB ffmpeg core is served from jsDelivr (`@ffmpeg/core-mt@0.12.10`, immutable URL, CORS *). Its three files were byte-identical to ours; the app now checks each file's sha256 before use and refuses a mismatch (tests incl. a drift guard against the installed package). The privacy page names the host.
4. **Referrer-Policy: no-referrer.** Found by running the live site: Hugging Face answers 404 (no CORS header) to any request whose Referer is a workers.dev address, so the first live model download failed (`real-run-before-referrer-fix/`). With no Referer it works; this also keeps the page address from reaching the model and core hosts. A custom domain would also have avoided it.
5. Home page, research section: the text "The final results are not in" and four "Not run yet" rows were false. Replaced with the real numbers: regex baseline 535/900 (59.4%), base model 0/900, ffwd 867/900 (96.3%) native and 95.0% in the browser, frontier model 866/900 (96.2%), labelled as 900 held-out generated tasks. It is your voice: please read it.

## Needs you
- Read the new home-page paragraph and results block (item 5).
- `pnpm check:release` still fails on the PostHog IP-capture note you chose to keep; Cloudflare does not run it.
- R2 (optional): if you want the core on your own host later, enable R2 in the dashboard and change VITE_FFMPEG_CORE_BASE; the hash pin still applies.
- Custom domain: none yet (no zone in the account). When you add one, update VITE_SITE_URL, the feedback Worker's ALLOWED_ORIGIN, and the R2 CORS if used.
- Feedback Worker (workers/feedback) is NOT deployed; the feedback buttons stay hidden until VITE_FEEDBACK_URL is set.
- Not done by me: flipping any repo public (the model repo on HF was already public when I checked; the GitHub repos are private), analytics, the GitHub release.
- I did not test: Firefox/Safari/phones, a non-NVIDIA computer on the live site, or the live CSP with the processor path.
