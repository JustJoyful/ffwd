import { readFileSync, writeFileSync } from "node:fs";
import { test } from "@playwright/test";

// Maintenance tool, not a test: captures `ffmpeg -hide_banner -i <clip>` output from ffmpeg.wasm for every corpus clip
// that has no log in tests/fixtures/ffmpeg-wasm-i-logs.json yet, and merges it into that file.
//   CAPTURE_I_LOGS=1 pnpm exec playwright test e2e/capture-i-logs.spec.ts
// One clip at a time with a fresh core, so the largest clip (125 MB) is the only big allocation.
const FIXTURE = "tests/fixtures/ffmpeg-wasm-i-logs.json";
const MANIFEST = "../../data/corpus/manifest.json";

test("capture ffmpeg.wasm -i logs for corpus clips missing from the fixture", async ({ page }) => {
  test.skip(!process.env.CAPTURE_I_LOGS, "set CAPTURE_I_LOGS=1 to run this maintenance tool");
  test.setTimeout(600_000);
  const logs: Record<string, string> = JSON.parse(readFileSync(FIXTURE, "utf8"));
  const files = (JSON.parse(readFileSync(MANIFEST, "utf8")) as { file: string }[])
    .map((r) => r.file)
    .filter((f) => !(f in logs));
  await page.goto("/");
  const CHUNK = 24 * 1024 * 1024; // Playwright's CDP pipe refuses messages over 100 MB (the 125 MB HEVC clip)
  for (const f of files) {
    const bytes = readFileSync(`../../data/corpus/${f}`);
    await page.evaluate(() => ((window as unknown as { __c: Uint8Array[] }).__c = []));
    for (let o = 0; o < bytes.length; o += CHUNK)
      await page.evaluate(
        (b64) => {
          const w = window as unknown as { __c: Uint8Array[] };
          w.__c.push(Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)));
        },
        bytes.subarray(o, o + CHUNK).toString("base64"),
      );
    logs[f] = await page.evaluate(async (name) => {
      type Spike = {
        loadFfmpeg(): Promise<any>; // eslint-disable-line @typescript-eslint/no-explicit-any
        execLogged(ff: any, a: string[]): Promise<{ log: string }>; // eslint-disable-line @typescript-eslint/no-explicit-any
      };
      const w = window as unknown as { spike: Spike; __c: Uint8Array[] };
      const ff = await w.spike.loadFfmpeg();
      await ff.writeFile(name, await new Blob(w.__c as BlobPart[]).bytes());
      w.__c = [];
      const r = await w.spike.execLogged(ff, ["-hide_banner", "-i", name]);
      ff.terminate();
      return r.log;
    }, f);
    console.log("captured", f);
  }
  writeFileSync(FIXTURE, JSON.stringify(logs, null, 2) + "\n");
});
