// Single config module for the browser spike (RULES §6.2).
export const PROTOCOL_VERSION = "0.1.0";
export const FFMPEG_CORE_BASE = "/ffmpeg"; // copied from @ffmpeg/core-mt by scripts/copy-core.mjs
// [VERIFY] present in the pinned WebLLM prebuiltAppConfig; the page records whether they are.
export const MODEL_IDS = ["Qwen3-0.6B-q4f16_1-MLC", "Qwen3-1.7B-q4f16_1-MLC"] as const;
// Re-encodes deadlock in core-mt 0.12.10 when FFmpeg auto-picks threads (found in Phase 0: copy
// works, every encode hangs). The harness caps threads on every output, like it owns -y.
export const FFMPEG_THREADS = 4;
export const MAX_RUNS = 4; // ARCH §3.1
export const MAX_TURNS = 8;
export const MAX_TOKENS = 512;
export const TIME_TOLERANCE_S = 0.15;
export const FRAME_COUNT_TOLERANCE = 1;
export const MINI_LOOP_TASKS = [
  { family: "F1", request: "cut the first 3 seconds off this video" },
  { family: "F4", request: "shrink this video to 480p" },
  { family: "F7", request: "take a frame every 2 seconds and save them as images" },
] as const;
