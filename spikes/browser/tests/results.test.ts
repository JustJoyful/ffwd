import { describe, expect, it } from "vitest";
import { parseFfmpegDuration, parseFrameCount, parseVideoSize } from "../src/results";

describe("ffmpeg log parsing", () => {
  it("parses ffmpeg duration", () => {
    expect(parseFfmpegDuration("  Duration: 00:00:20.05, start: 0.000000")).toBeCloseTo(20.05);
    expect(parseFfmpegDuration("  Duration: 01:02:03.50, start")).toBeCloseTo(3723.5);
    expect(parseFfmpegDuration("garbage")).toBeNull();
  });
  it("parses the output video size from the last Stream line", () => {
    const log =
      "Stream #0:0: Video: h264, yuv420p, 1920x1080\nStream #0:0: Video: h264, yuv420p(tv), 1280x720 [SAR 1:1]";
    expect(parseVideoSize(log)).toEqual([1280, 720]);
    expect(parseVideoSize("no video")).toBeNull();
  });
  it("counts written frames from the final progress line", () => {
    expect(
      parseFrameCount("frame=    3 fps=0.0 q=-0.0 size=...\nframe=    5 fps=0.0 q=-0.0 Lsize=N/A"),
    ).toBe(5);
    expect(parseFrameCount("")).toBeNull();
  });
});
