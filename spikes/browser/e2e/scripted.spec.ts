import { existsSync } from "node:fs";
import { expect, test } from "@playwright/test";

const long = "../../data/corpus/h264_long.mp4";

// Proves model → validated run → ffmpeg.wasm → check works for F1/F4/F7 with a scripted "model".
test("scripted loop reaches ffmpeg and passes for F1, F4, F7", async ({ page }) => {
  test.skip(!existsSync(long), "generate the corpus first");
  test.setTimeout(120_000);
  await page.goto("/");
  await page.setInputFiles("#long-file", long);
  await page.click("#run-scripted");
  await expect(page.locator("#status")).toHaveText(/scripted loop: (done|failed)/, {
    timeout: 110_000,
  });
  const lines = await page.locator("#log li").allTextContents();
  for (const f of ["F1", "F4", "F7"]) {
    const l = lines.find((x) => x.includes(`mini_loop_${f}_scripted`));
    expect(l, f).toMatch(/^✓/);
    expect(l, f).toContain('"modelPassed":true');
    expect(l, f).toContain('"ended":"finish"');
  }
});
