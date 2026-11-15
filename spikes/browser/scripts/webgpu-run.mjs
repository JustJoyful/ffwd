// Drives the deployed spike page in a headed Chromium with WebGPU and saves the results JSON.
// Run it inside a memory-capped systemd unit (see README in reports) so a tab blow-up can't take the desktop.
//   MODEL=Qwen3-0.6B-q4f16_1-MLC JSON_MODE=0 LABEL=owner-desktop-0.6b node scripts/webgpu-run.mjs
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const {
  MODEL,
  JSON_MODE = "0",
  LABEL,
  PAGE_URL = "https://ffmpeg-agent-spike.pages.dev/",
  OUT,
} = process.env;
const exe = process.env.CHROME_EXE;
const corpus = new URL("../../../data/corpus/", import.meta.url).pathname;
const ctx = await chromium.launchPersistentContext(`/tmp/ffagent-chrome-${LABEL}`, {
  headless: false,
  executablePath: exe,
  acceptDownloads: true,
  args: [
    "--enable-unsafe-webgpu",
    "--enable-features=Vulkan,WebGPU",
    "--use-angle=vulkan",
    "--ozone-platform=x11",
  ],
});
const page = await ctx.newPage();
page.on("pageerror", (e) => console.log("[pageerror]", e.message));
await page.goto(PAGE_URL);
await page.setInputFiles("#long-file", `${corpus}h264_long.mp4`);
await page.selectOption("#model", MODEL);
if (JSON_MODE === "1") await page.check("#json-mode");
await page.fill("#machine", LABEL);
await page.click("#run-model");
await page.waitForFunction(
  () => /model checks: (done|failed)/.test(document.querySelector("#status")?.textContent ?? ""),
  null,
  {
    timeout: 20 * 60_000,
    polling: 2000,
  },
);
console.log(await page.locator("#status").textContent());
for (const l of await page.locator("#log li").allTextContents()) console.log(l.slice(0, 260));
const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#download")]);
mkdirSync(OUT, { recursive: true });
await dl.saveAs(`${OUT}/${dl.suggestedFilename()}`);
console.log("saved", `${OUT}/${dl.suggestedFilename()}`);
await ctx.close();
