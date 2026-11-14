import { existsSync } from "node:fs";
import { expect, test } from "@playwright/test";

const CORPUS = "../../data/corpus";
const hevc = `${CORPUS}/hevc_iphone.mov`;
const long = `${CORPUS}/h264_long.mp4`;

test("ffmpeg.wasm MT loads, decodes HEVC and runs the timing chores", async ({ page }) => {
  test.skip(
    !existsSync(hevc) || !existsSync(long),
    "run `uv run python -m training.corpus.make_synthetic data/corpus` first",
  );
  test.setTimeout(240_000);
  page.on("console", (m) => console.log(`[page:${m.type()}] ${m.text()}`));
  let workers = 0;
  page.on("worker", () => workers++);
  test.info().annotations.push({ type: "note", description: "workers counted" });
  page.on("pageerror", (e) => console.log(`[pageerror] ${e.message}`));
  await page.goto("/");
  await page.setInputFiles("#hevc-file", hevc);
  await page.setInputFiles("#long-file", long);
  await page.click("#run-ffmpeg");
  try {
    await expect(page.locator("#status")).toHaveText(/ffmpeg checks: (done|failed)/, {
      timeout: Number(process.env.FFMPEG_E2E_TIMEOUT ?? 230_000),
    });
  } finally {
    console.log(`workers spawned: ${workers}`);
    console.log((await page.locator("#log li").allTextContents()).join("\n"));
  }
  const lines = await page.locator("#log li").allTextContents();
  for (const name of [
    "ffmpeg_mt_load",
    "cross_origin_isolated",
    "chore_F1-trim-copy",
    "chore_F4-scale-480p",
    "chore_F7-frames-every-2s",
  ]) {
    expect(
      lines.find((l) => l.includes(name)),
      name,
    ).toMatch(/^✓/);
  }
});
