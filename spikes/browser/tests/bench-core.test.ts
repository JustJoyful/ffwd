import { describe, expect, it } from "vitest";
import { gpuDecision, peakBytes, splitLoadPhases } from "../src/bench-core";

describe("splitLoadPhases (WebLLM progress messages -> download / weights / shader / init)", () => {
  const ev = (t: number, text: string) => ({ t, text });

  it("splits a cold load", () => {
    const events = [
      ev(2_000, "Start to fetch params"),
      ev(2_100, "Fetching param cache[1/5]: 10MB fetched. 10% completed, 0 secs elapsed."),
      ev(30_000, "Fetching param cache[5/5]: 350MB fetched. 100% completed, 28 secs elapsed."),
      ev(31_000, "Loading model from cache[1/5]: 70MB loaded. 20% completed, 29 secs elapsed."),
      ev(33_000, "Loading model from cache[5/5]: 350MB loaded. 100% completed, 31 secs elapsed."),
      ev(33_500, "Loading GPU shader modules[1/20]: 5% completed, 0 secs elapsed."),
      ev(40_000, "Loading GPU shader modules[20/20]: 100% completed, 6 secs elapsed."),
    ];
    const r = splitLoadPhases(events, 42_000);
    expect(r.cold).toBe(true);
    expect(r.download_ms).toBe(31_000 - 2_000); // first message .. first "Loading model" message
    expect(r.weights_load_ms).toBe(33_500 - 31_000);
    expect(r.shader_ms).toBe(40_000 - 33_500);
    expect(r.init_ms).toBe(2_000 + (42_000 - 40_000)); // setup before the first message + work after the last
    expect(r.download_ms + r.weights_load_ms + r.shader_ms + r.init_ms).toBe(42_000); // nothing lost or double counted
  });

  it("a warm load has no download phase", () => {
    const events = [
      ev(500, "Start to fetch params"),
      ev(600, "Loading model from cache[1/5]: 70MB loaded. 20% completed, 0 secs elapsed."),
      ev(1_500, "Loading GPU shader modules[1/20]: 5% completed, 0 secs elapsed."),
      ev(3_000, "Loading GPU shader modules[20/20]: 100% completed, 1 secs elapsed."),
    ];
    const r = splitLoadPhases(events, 3_400);
    expect(r.cold).toBe(false);
    expect(r.download_ms).toBe(0);
    expect(r.weights_load_ms + r.shader_ms + r.init_ms + r.download_ms).toBe(3_400);
  });

  it("copes with no events at all", () => {
    expect(splitLoadPhases([], 1234)).toEqual({
      cold: false,
      download_ms: 0,
      weights_load_ms: 0,
      shader_ms: 0,
      init_ms: 1234,
    });
  });
});

describe("gpuDecision: the discrete-GPU policy is a flag, default warn-and-allow", () => {
  it("proceeds on a discrete GPU without a warning", () => {
    expect(gpuDecision("nvidia", "refuse")).toEqual({
      proceed: true,
      warning: null,
      gpuClass: "discrete",
    });
    expect(gpuDecision("amd", "warn")).toEqual({
      proceed: true,
      warning: null,
      gpuClass: "discrete",
    });
  });
  it("warn policy lets an integrated GPU run but says so", () => {
    const d = gpuDecision("intel", "warn");
    expect(d.proceed).toBe(true);
    expect(d.gpuClass).toBe("integrated");
    expect(d.warning).toMatch(/integrated/i);
  });
  it("refuse policy stops an integrated GPU", () => {
    expect(gpuDecision("intel", "refuse").proceed).toBe(false);
  });
  it("unknown or missing adapters: allowed under warn, refused under refuse", () => {
    expect(gpuDecision(null, "warn").proceed).toBe(true);
    expect(gpuDecision(null, "refuse").proceed).toBe(false);
    expect(gpuDecision("apple", "refuse")).toMatchObject({ proceed: true, gpuClass: "unified" });
  });
});

describe("peakBytes", () => {
  it("takes the max and ignores failed samples", () => {
    expect(peakBytes([100, null, 400, 250])).toBe(400);
    expect(peakBytes([])).toBeNull();
    expect(peakBytes([null, null])).toBeNull();
  });
});
