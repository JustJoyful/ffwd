// Runs the Phase 2 bench page in a headed Chromium with WebGPU and saves one results JSON.
//   LABEL=owner-desktop MODEL=Qwen3-0.6B-q4f16_1-MLC BENCH_DIR=data/bench OUT=reports/.../bench node scripts/bench-run.mjs
// Add GPU_POLICY=refuse to test the strict policy. Run inside a memory-capped systemd unit.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const {
  LABEL,
  MODEL,
  BENCH_DIR,
  OUT,
  GPU_POLICY = "warn",
  PAGE_URL = "https://ffmpeg-agent-spike.pages.dev/",
} = process.env;
const ctx = await chromium.launchPersistentContext(
  `${process.env.HOME}/.cache/ffagent-chrome-bench-${LABEL}`,
  {
    headless: false,
    executablePath: process.env.CHROME_EXE,
    acceptDownloads: true,
    args: [
      "--enable-unsafe-webgpu",
      "--enable-features=Vulkan,WebGPU",
      "--use-angle=vulkan",
      "--ozone-platform=x11",
    ],
  },
);
const page = await ctx.newPage();
page.on("pageerror", (e) => console.log("[pageerror]", e.message));
await page.goto(`${PAGE_URL}?gpuPolicy=${GPU_POLICY}`);
await page.click("#clear-saved");
for (const [id, f] of [
  ["bench-hevc1080", "hevc_1080p_60s.mov"],
  ["bench-hevc4k", "hevc_4k_60s.mov"],
  ["bench-h264-100mb", "h264_100mb_60s.mp4"],
  ["bench-h264-500mb", "h264_500mb_60s.mp4"],
]) {
  await page.setInputFiles(`#${id}`, `${BENCH_DIR}/${f}`);
}
await page.selectOption("#model", MODEL);
await page.fill("#machine", LABEL);
await page.click("#run-bench");
await page.waitForFunction(
  () => /bench: (done|failed)/.test(document.querySelector("#status")?.textContent ?? ""),
  null,
  {
    timeout: 90 * 60_000,
    polling: 5000,
  },
);
for (const l of await page.locator("#log li").allTextContents()) console.log(l.slice(0, 300));
const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#download")]);
mkdirSync(OUT, { recursive: true });
await dl.saveAs(`${OUT}/bench-${LABEL}.json`);
console.log("saved", `${OUT}/bench-${LABEL}.json`);
await ctx.close();
