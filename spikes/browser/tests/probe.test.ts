import { describe, expect, it } from "vitest";
import logs from "./fixtures/ffmpeg-wasm-i-logs.json";
import manifest from "../../../data/corpus/manifest.json";
import { parseFfmpegProbe } from "../src/probe";

// Real `ffmpeg -hide_banner -i <clip>` output captured from @ffmpeg/core-mt 0.12.10 (FFmpeg 5.1.4)
// for every corpus clip. The expected values are the PYTHON probe (ffprobe, native FFmpeg 9)
// stored in data/corpus/manifest.json: both runtimes must describe the same file the same way.
type Rec = { id: string; file: string; probe: PyProbe };
type PyStream = Record<string, unknown> & { type: string; index: number };
type PyProbe = { container: string; duration_s: number; streams: PyStream[] };

describe("browser probe parser agrees with the Python probe", () => {
  const records = manifest as unknown as Rec[];
  it("has a log for every manifest clip", () => {
    for (const r of records)
      expect((logs as Record<string, string>)[r.file], r.file).toBeTypeOf("string");
  });

  it.each(records.map((r) => [r.id, r] as const))("%s", (_id, r) => {
    const got = parseFfmpegProbe((logs as Record<string, string>)[r.file] as string);
    expect(got.container).toBe(r.probe.container);
    expect(got.duration_s).toBeCloseTo(r.probe.duration_s, 1);
    expect(got.streams.map((s) => s.type)).toEqual(r.probe.streams.map((s) => s.type));
    r.probe.streams.forEach((want, i) => {
      const s = got.streams[i] as unknown as Record<string, unknown>;
      expect(s.codec, `${r.id} stream ${i} codec`).toBe(want.codec);
      if (want.type === "video") {
        for (const k of ["width", "height", "pix_fmt", "rotation"])
          expect(s[k], `${r.id} ${k}`).toBe(want[k]);
        expect(s.fps as number).toBeCloseTo(want.fps as number, 1);
      } else {
        expect(s.sample_rate, `${r.id} sample_rate`).toBe(want.sample_rate);
        expect(s.channels, `${r.id} channels`).toBe(want.channels);
      }
    });
  });

  it("reads rotation from the displaymatrix side data (iPhone-style clip)", () => {
    const rot = parseFfmpegProbe((logs as Record<string, string>)["hevc_rot90.mov"] as string);
    expect(rot.streams[0]).toMatchObject({ width: 1920, height: 1080, rotation: 90 });
  });

  it("normalises negative rotations and tolerates garbage", () => {
    const neg =
      "Input #0, mov,mp4, from 'x.mov':\n  Duration: 00:00:01.00, start: 0.0, bitrate: 1 kb/s\n  Stream #0:0: Video: h264, yuv420p, 100x50, 25 fps\n    Side data:\n      displaymatrix: rotation of -90.00 degrees\n";
    expect(parseFfmpegProbe(neg).streams[0]).toMatchObject({ rotation: 270 });
    expect(() => parseFfmpegProbe("not an ffmpeg log")).toThrow(/no input/i);
  });
});
