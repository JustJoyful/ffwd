// Phase 2 bench: run on each machine, download ONE JSON per machine (results.ts downloadResults).
// Steps run safest-first and each is isolated: a failure is recorded and the bench continues. If the tab
// dies (the 500 MB input can), results so far are in localStorage and a "step in flight" marker names the culprit.
import type { FFmpeg } from "@ffmpeg/ffmpeg";
import { fetchFile } from "@ffmpeg/util";
import { peakBytes } from "./bench-core";
import {
  BENCH_FFMPEG_ARGS,
  BENCH_MEMORY_SAMPLE_MS,
  BENCH_STEP_TIMEOUT_MS,
  gpuPolicy,
} from "./config";
import { execLogged, loadFfmpeg } from "./ffmpeg-check";
import { harnessArgs } from "./harness-args";
import { record } from "./results";
import { checkGpu, loadModel, measureSpeed } from "./webllm-check";

export type BenchFiles = Partial<Record<"hevc1080" | "hevc4k" | "h264_100mb" | "h264_500mb", File>>;

const INFLIGHT = "ffagent-bench-inflight";
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Call once at page load: if the previous tab died mid-step, say which step. */
export function reportCrash(): void {
  try {
    const marker = localStorage.getItem(INFLIGHT);
    if (marker) {
      record({
        name: "previous_tab_crash",
        ok: false,
        detail: JSON.parse(marker) as Record<string, unknown>,
      });
      localStorage.removeItem(INFLIGHT);
    }
  } catch {
    /* storage unavailable */
  }
}

async function step(name: string, fn: () => Promise<void>): Promise<void> {
  try {
    localStorage.setItem(INFLIGHT, JSON.stringify({ step: name, at: new Date().toISOString() }));
  } catch {
    /* ignore */
  }
  try {
    await fn();
  } catch (e) {
    record({ name: `${name}_error`, ok: false, detail: { error: String(e) } });
  }
  try {
    localStorage.removeItem(INFLIGHT);
  } catch {
    /* ignore */
  }
}

type MemoryApi = { measureUserAgentSpecificMemory?: () => Promise<{ bytes: number }> };
async function measureBytes(): Promise<number | null> {
  try {
    return (
      (await (performance as Performance & MemoryApi).measureUserAgentSpecificMemory?.())?.bytes ??
      null
    );
  } catch {
    return null;
  }
}

/** Run `work` while sampling tab memory; returns the peak of the samples (measureUserAgentSpecificMemory). */
async function withMemory<T>(
  work: Promise<T>,
): Promise<{ result: T; peak: number | null; samples: number }> {
  const samples: (number | null)[] = [await measureBytes()];
  let done = false;
  const guarded = work.finally(() => {
    done = true;
  });
  const sampler = (async () => {
    while (!done) {
      samples.push(await measureBytes());
      await sleep(BENCH_MEMORY_SAMPLE_MS);
    }
  })();
  let error: unknown;
  let result: T | undefined;
  try {
    result = await guarded;
  } catch (e) {
    error = e;
  }
  await sampler;
  samples.push(await measureBytes());
  if (error !== undefined) throw error;
  return { result: result as T, peak: peakBytes(samples), samples: samples.length };
}

/** Write a user file into ffmpeg.wasm, run one harness-validated command, record time/size/peak memory. */
async function timedJob(
  holder: { ff: FFmpeg },
  recordName: string,
  file: File,
  args: string[],
): Promise<void> {
  const inName = "bench_in" + (file.name.match(/\.[a-z0-9]+$/i)?.[0] ?? ".mp4");
  const outName = "bench_out.mp4";
  const ff = holder.ff;
  await ff.writeFile(inName, await fetchFile(file));
  const {
    result: r,
    peak,
    samples,
  } = await withMemory(execLogged(ff, harnessArgs(args, inName, outName), BENCH_STEP_TIMEOUT_MS));
  const outBytes =
    r.code === 0
      ? ((await ff.readFile(outName).catch(() => new Uint8Array())) as Uint8Array).byteLength
      : 0;
  record({
    name: recordName,
    ok: r.code === 0 && outBytes > 0,
    ms: r.ms,
    detail: {
      file: file.name,
      inputBytes: file.size,
      outputBytes: outBytes,
      peakBytesUserAgent: peak,
      memorySamples: samples,
      code: r.code,
      timedOut: r.code !== 0 && r.ms >= BENCH_STEP_TIMEOUT_MS,
    },
  });
  await ff.deleteFile(inName).catch(() => undefined);
  await ff.deleteFile(outName).catch(() => undefined);
  if (r.code !== 0) {
    // A timed-out or failed exec can leave the wasm instance unusable: start a fresh core for later steps.
    ff.terminate();
    holder.ff = await loadFfmpeg();
  }
}

export async function runBench(
  files: BenchFiles,
  modelId: string,
  onStatus: (t: string) => void,
): Promise<void> {
  let gpuOk = false;
  await step("gpu", async () => {
    await checkGpu(gpuPolicy());
    gpuOk = true;
  });
  if (gpuOk) {
    await step("model_cold", async () => {
      onStatus("model: cold load (clears the cache first)");
      const engine = await loadModel(modelId, onStatus, { forceCold: true, label: "cold" });
      await measureSpeed(engine, modelId);
      await engine.unload();
    });
    await step("model_warm", async () => {
      onStatus("model: warm load");
      const engine = await loadModel(modelId, onStatus, { label: "warm" });
      await engine.unload();
    });
  }
  const holder = { ff: await loadFfmpeg() };
  const jobs: [keyof BenchFiles, string, string[]][] = [
    ["hevc1080", "bench_hevc_1080p_60s_to_h264", BENCH_FFMPEG_ARGS.hevcToH264],
    ["h264_100mb", "bench_f4_480p_60s_input100mb", BENCH_FFMPEG_ARGS.f4Scale480],
    ["hevc4k", "bench_hevc_4k_60s_to_h264", BENCH_FFMPEG_ARGS.hevcToH264],
    ["h264_500mb", "bench_f4_480p_60s_input500mb", BENCH_FFMPEG_ARGS.f4Scale480],
  ];
  for (const [key, name, args] of jobs) {
    const file = files[key];
    if (!file) {
      record({ name, ok: false, detail: { skipped: "no file chosen" } });
      continue;
    }
    await step(name, async () => {
      onStatus(`${name} (${Math.round(file.size / 1e6)} MB input)`);
      await timedJob(holder, name, file, args);
    });
  }
}
