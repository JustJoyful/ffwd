import type { FFmpeg } from "@ffmpeg/ffmpeg";
import { execLogged } from "./ffmpeg-check";

// Browser probe: parses `ffmpeg -hide_banner -i <file>` output (exits 1 "no output file", by design)
// into the same shape as the Python probe (training/env/probe.py, probe.schema.json subset).
// Chosen over ffprobe() after measurement, see reports/2026-11-16-phase0-followups/summary.md.
export type ProbeStream = {
  index: number;
  type: "video" | "audio" | "subtitle" | "data" | "attachment" | "unknown";
  codec: string | null;
  width?: number;
  height?: number;
  fps?: number | null;
  pix_fmt?: string | null;
  rotation?: number;
  sample_rate?: number | null;
  channels?: number | null;
};
export type BrowserProbe = {
  container: string;
  duration_s: number | null;
  bit_rate: number | null;
  streams: ProbeStream[];
};

const KINDS: Record<string, ProbeStream["type"]> = {
  Video: "video",
  Audio: "audio",
  Subtitle: "subtitle",
  Data: "data",
  Attachment: "attachment",
};
const LAYOUT_CHANNELS: Record<string, number> = {
  mono: 1,
  stereo: 2,
  "2.1": 3,
  "5.1": 6,
  "7.1": 8,
};

/** Split on commas that are not inside (...) or [...]: "yuv420p(tv, progressive)" stays one part. */
function splitTopLevel(s: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let cur = "";
  for (const ch of s) {
    if (ch === "(" || ch === "[") depth++;
    else if (ch === ")" || ch === "]") depth--;
    if (ch === "," && depth === 0) {
      parts.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  parts.push(cur.trim());
  return parts;
}

const normaliseRotation = (deg: number): number =>
  (((Math.round(deg / 90) * 90) % 360) + 360) % 360;

export function parseFfmpegProbe(log: string): BrowserProbe {
  const input = /^Input #0, (.+?), from /m.exec(log);
  if (!input) throw new Error("no input description in ffmpeg log");
  const dur = /Duration: (\d+):(\d{2}):(\d{2}(?:\.\d+)?)/.exec(log);
  const br = /bitrate: (\d+) kb\/s/.exec(log);
  const streams: ProbeStream[] = [];
  let current: ProbeStream | null = null;
  for (const line of log.split("\n")) {
    const m = /^\s*Stream #0:(\d+)[^:]*: (\w+): (.*)$/.exec(line);
    if (m) {
      const type = KINDS[m[2] as string] ?? "unknown";
      const parts = splitTopLevel(m[3] as string);
      const s: ProbeStream = {
        index: Number(m[1]),
        type,
        codec: (parts[0] ?? "").split(" ")[0] || null,
      };
      if (type === "video") {
        s.pix_fmt = (parts[1] ?? "").split("(")[0] || null;
        const size = parts.map((p) => /^(\d{2,5})x(\d{2,5})/.exec(p)).find(Boolean);
        s.width = size ? Number(size[1]) : undefined;
        s.height = size ? Number(size[2]) : undefined;
        const fps = parts.map((p) => /^(\d+(?:\.\d+)?) fps/.exec(p)).find(Boolean);
        s.fps = fps ? Number(fps[1]) : null;
        s.rotation = 0;
      } else if (type === "audio") {
        const hz = parts.map((p) => /^(\d+) Hz/.exec(p)).find(Boolean);
        s.sample_rate = hz ? Number(hz[1]) : null;
        const ch = parts
          .map((p) => LAYOUT_CHANNELS[p] ?? /^(\d+) channels/.exec(p)?.[1])
          .find((x) => x !== undefined);
        s.channels = ch === undefined ? null : Number(ch);
      }
      streams.push(s);
      current = s;
      continue;
    }
    const rot = /displaymatrix: rotation of (-?[\d.]+) degrees/.exec(line);
    if (rot && current?.type === "video") current.rotation = normaliseRotation(Number(rot[1]));
  }
  return {
    container: input[1] as string,
    duration_s: dur ? Number(dur[1]) * 3600 + Number(dur[2]) * 60 + Number(dur[3]) : null,
    bit_rate: br ? Number(br[1]) * 1000 : null,
    streams,
  };
}

/** Probe via `ffmpeg -i` (the chosen strategy). Exit code 1 and "Aborted()" in the log are expected. */
export async function probeViaLog(ff: FFmpeg, name: string): Promise<BrowserProbe> {
  const { log } = await execLogged(ff, ["-hide_banner", "-i", name]);
  return parseFfmpegProbe(log);
}

/** The alternative, kept only for the measurement in e2e/probe.spec.ts: ffprobe JSON via the ffprobe entry point. */
export async function ffprobeJson(ff: FFmpeg, name: string): Promise<string> {
  await ff.ffprobe([
    "-v",
    "error",
    "-print_format",
    "json",
    "-show_format",
    "-show_streams",
    name,
    "-o",
    "probe.json",
  ]);
  const text = (await ff.readFile("probe.json", "utf8")) as string;
  await ff.deleteFile("probe.json");
  return text;
}
