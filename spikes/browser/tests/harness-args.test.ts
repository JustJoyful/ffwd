import { describe, expect, it } from "vitest";
import { FFMPEG_DECODE_THREADS, FFMPEG_THREADS } from "../src/config";
import { capThreads, harnessArgs } from "../src/harness-args";

// The thread cap is a HARNESS workaround, never something the model emits: re-encodes deadlock in
// @ffmpeg/core-mt 0.12.10 when FFmpeg auto-picks threads (Phase 0 finding, D-019 notes; see
// reports/2026-11-15-phase-0/summary.md). These tests pin the behaviour.
describe("thread cap injected by the harness", () => {
  it("inserts -threads N immediately before every output token", () => {
    expect(capThreads(["-i", "{in:a}", "-c:v", "libx264", "{out:o}"], 4)).toEqual([
      "-threads",
      "1",
      "-i",
      "{in:a}",
      "-c:v",
      "libx264",
      "-threads",
      "4",
      "{out:o}",
    ]);
    expect(capThreads(["-i", "{in:a}", "{out:a}", "-an", "{out:b}"], 2)).toEqual([
      "-threads",
      "1",
      "-i",
      "{in:a}",
      "-threads",
      "2",
      "{out:a}",
      "-an",
      "-threads",
      "2",
      "{out:b}",
    ]);
  });

  it("uses the configured default", () => {
    expect(capThreads(["-i", "{in:a}", "{out:o}"]).slice(-3)).toEqual([
      "-threads",
      String(FFMPEG_THREADS),
      "{out:o}",
    ]);
  });

  it("wins over a model-supplied -threads: the last one before the output is the harness cap", () => {
    const args = harnessArgs(
      ["-i", "{in:a}", "-threads", "64", "-c:v", "libx264", "{out:o}"],
      "in.mp4",
      "out.mp4",
    );
    const outAt = args.indexOf("out.mp4");
    expect(args.slice(outAt - 2, outAt + 1)).toEqual([
      "-threads",
      String(FFMPEG_THREADS),
      "out.mp4",
    ]);
    expect(args.lastIndexOf("-threads")).toBe(outAt - 2);
  });

  it("substitutes ids with in-memory names and leaves everything else alone", () => {
    expect(
      harnessArgs(["-ss", "3", "-i", "{in:clip}", "-c", "copy", "{out:out1}"], "in.mp4", "o.mp4"),
    ).toEqual([
      "-ss",
      "3",
      "-threads",
      String(FFMPEG_DECODE_THREADS),
      "-i",
      "in.mp4",
      "-c",
      "copy",
      "-threads",
      String(FFMPEG_THREADS),
      "o.mp4",
    ]);
  });

  it("caps decoder threads before EVERY input (two-input concat deadlocks otherwise)", () => {
    const args = harnessArgs(
      [
        "-i",
        "{in:a}",
        "-i",
        "{in:b}",
        "-filter_complex",
        "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "{out:o}",
      ],
      "in.mp4",
      "o.mp4",
    );
    const cap = ["-threads", String(FFMPEG_DECODE_THREADS)];
    const at = args.flatMap((a, i) => (a === "-i" ? [args.slice(i - 2, i)] : []));
    expect(at).toEqual([cap, cap]);
  });
});
