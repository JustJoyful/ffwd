import { expect, test } from "@playwright/test";

test("page is cross-origin isolated", async ({ page }) => {
  await page.goto("/");
  expect(await page.evaluate(() => crossOriginIsolated)).toBe(true);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "ffmpeg-agent Phase 0 browser spike",
  );
});
