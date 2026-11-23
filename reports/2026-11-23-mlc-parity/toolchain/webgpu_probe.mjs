// WebGPU feasibility probe (23 Nov 2026). Run from spikes/browser (it has @playwright/test): `node webgpu_probe.mjs`.
// navigator.gpu only exists in a SECURE context, so about:blank reports gpu:false whatever the flags; we serve a
// stub page at http://localhost:4321/ through page.route (localhost counts as secure).
import { chromium } from "@playwright/test";

const variants = [
  ["headless-shell, no flags", { headless: true, args: [] }],
  ["new-headless, unsafe-webgpu + Vulkan", { headless: true, channel: "chromium", args: ["--enable-unsafe-webgpu", "--enable-features=Vulkan"] }],
  ["new-headless, A: unsafe-webgpu + Vulkan + use-angle=vulkan", { headless: true, channel: "chromium", args: ["--enable-unsafe-webgpu", "--enable-features=Vulkan", "--use-angle=vulkan"] }],
  ["new-headless, B: unsafe-webgpu + Vulkan + ignore-gpu-blocklist", { headless: true, channel: "chromium", args: ["--enable-unsafe-webgpu", "--enable-features=Vulkan", "--ignore-gpu-blocklist"] }],
  ["new-headless, C: ignore-gpu-blocklist only", { headless: true, channel: "chromium", args: ["--ignore-gpu-blocklist"] }],
  ["headless-shell, D: unsafe-webgpu + Vulkan + use-angle=vulkan + ignore-gpu-blocklist", { headless: true, args: ["--enable-unsafe-webgpu", "--enable-features=Vulkan", "--use-angle=vulkan", "--ignore-gpu-blocklist"] }],
  ["headed, no flags", { headless: false, args: [] }],
  ["headed, unsafe-webgpu + Vulkan", { headless: false, args: ["--enable-unsafe-webgpu", "--enable-features=Vulkan"] }],
];
for (const [name, opts] of variants) {
  let browser;
  try {
    browser = await chromium.launch(opts);
    const page = await browser.newPage();
    await page.route("http://localhost:4321/", (r) => r.fulfill({ contentType: "text/html", body: "<html></html>" }));
    await page.goto("http://localhost:4321/");
    const r = await page.evaluate(async () => {
      if (!navigator.gpu) return { gpu: false };
      const a = await navigator.gpu.requestAdapter();
      if (!a) return { gpu: true, adapter: null };
      const info = a.info ?? {};
      return { gpu: true, adapter: true, vendor: info.vendor, architecture: info.architecture, fallback: a.isFallbackAdapter, shaderF16: a.features.has("shader-f16"), maxBufferSize: a.limits.maxBufferSize, maxStorageBufferBindingSize: a.limits.maxStorageBufferBindingSize };
    });
    console.log(name, "=>", JSON.stringify(r));
  } catch (e) {
    console.log(name, "=> ERROR", String(e).split("\n")[0].slice(0, 160));
  } finally {
    await browser?.close();
  }
}
