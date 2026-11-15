// Production loads the core from the CDN; Pages rejects the 31 MiB wasm, so keep it out of dist.
import { rmSync } from "node:fs";
rmSync("dist/ffmpeg", { recursive: true, force: true });
