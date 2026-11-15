import { FFmpeg } from "@ffmpeg/ffmpeg";
import { fetchFile, toBlobURL } from "@ffmpeg/util";
import chores from "../../../packages/protocol/conformance/timing-chores.json";
import { FFMPEG_CORE_BASE } from "./config";
import { harnessArgs } from "./harness-args";
import { record } from "./results";
import { validateRun } from "./validator";

export type Exec = { code: number; log: string; ms: number };

export async function loadFfmpeg(): Promise<FFmpeg> {
  const ff = new FFmpeg();
  const t0 = performance.now();
  try {
    // Blob URLs for core, wasm and the pthread worker, as the ffmpeg.wasm docs do for core-mt.
    const url = (f: string, type: string) => toBlobURL(`${FFMPEG_CORE_BASE}/${f}`, type);
    await ff.load({
      coreURL: await url("ffmpeg-core.js", "text/javascript"),
      wasmURL: await url("ffmpeg-core.wasm", "application/wasm"),
      workerURL: await url("ffmpeg-core.worker.js", "text/javascript"),
    });
    record({ name: "ffmpeg_mt_load", ok: true, ms: performance.now() - t0 });
  } catch (e) {
    record({ name: "ffmpeg_mt_load", ok: false, detail: { error: String(e) } });
    throw e;
  }
  return ff;
}

export async function execLogged(ff: FFmpeg, args: string[]): Promise<Exec> {
  let log = "";
  const onLog = ({ message }: { message: string }) => (log += message + "\n");
  ff.on("log", onLog);
  const t0 = performance.now();
  try {
    const code = await ff.exec(args);
    return { code, log, ms: performance.now() - t0 };
  } finally {
    ff.off("log", onLog);
  }
}

export async function outputBytes(ff: FFmpeg, outName: string): Promise<number> {
  if (outName.includes("%")) {
    const dir = outName.split("/")[0] as string;
    const entries = await ff.listDir(dir);
    return entries.filter((e) => !e.isDir).length;
  }
  return ((await ff.readFile(outName)) as Uint8Array).byteLength;
}

export async function runFfmpegChecks(
  ff: FFmpeg,
  hevc: File | null,
  long: File | null,
): Promise<void> {
  record({ name: "cross_origin_isolated", ok: self.crossOriginIsolated });
  if (long) {
    await ff.writeFile("long.mp4", await fetchFile(long));
    for (const c of chores) {
      const v = validateRun(c.args, ["clip"], ["out1"], {
        inputs: new Set(["clip"]),
        outputs: new Set(["out1"]),
      });
      if (!v.ok) {
        record({ name: `chore_${c.name}`, ok: false, detail: { rejected: v.reason } });
        continue;
      }
      if (c.output.includes("/"))
        await ff.createDir(c.output.split("/")[0] as string).catch(() => undefined);
      const r = await execLogged(ff, harnessArgs(c.args, "long.mp4", c.output));
      record({ name: `chore_${c.name}`, ok: r.code === 0, ms: r.ms, detail: { code: r.code } });
    }
  }
  if (hevc) {
    await ff.writeFile("hevc.mov", await fetchFile(hevc));
    const r = await execLogged(
      ff,
      harnessArgs(
        ["-i", "{in:clip}", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "{out:out1}"],
        "hevc.mov",
        "hevc_out.mp4",
      ),
    );
    const bytes = r.code === 0 ? await outputBytes(ff, "hevc_out.mp4").catch(() => 0) : 0;
    record({
      name: "hevc_decode",
      ok: r.code === 0 && bytes > 0,
      ms: r.ms,
      detail: { code: r.code, bytes, logTail: r.log.slice(-400) },
    });
  }
  // Last on purpose: in core-mt 0.12.10 ffprobe ends with Aborted(), which can poison later execs.
  try {
    const code = await ff.ffprobe(["-version"]);
    record({
      name: "ffprobe_available",
      ok: code === 0,
      detail: { code, ffmpegPkg: "0.12.15", core: "core-mt 0.12.10" },
    });
  } catch (e) {
    record({ name: "ffprobe_available", ok: false, detail: { error: String(e) } });
  }
}
