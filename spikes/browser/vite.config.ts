import { defineConfig } from "vitest/config";

// Multithreaded ffmpeg.wasm needs SharedArrayBuffer, which needs cross-origin isolation (ARCH §4).
// `credentialless` COEP lets WebLLM fetch model weights from Hugging Face without CORP headers [VERIFY].
// The same headers ship to Cloudflare Pages via public/_headers.
const isolation = {
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Embedder-Policy": "credentialless",
};

export default defineConfig({
  server: { headers: isolation, fs: { allow: ["../.."] } }, // protocol files live in packages/protocol
  preview: { headers: isolation },
  optimizeDeps: { exclude: ["@ffmpeg/ffmpeg", "@ffmpeg/util"] },
  worker: { format: "es" }, // ffmpeg.wasm and WebLLM workers use ES module imports
  test: { include: ["tests/**/*.test.ts"] },
});
