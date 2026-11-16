// Pure logic for the Phase 2 bench (no browser APIs, so it is unit-tested).

import type { GpuPolicy } from "./config";

export type { GpuPolicy };
export type GpuClass = "discrete" | "integrated" | "unified" | "unknown";

/** Vendor string from navigator.gpu adapter info -> class. WebGPU exposes no "is discrete" bit. */
export function gpuDecision(
  vendor: string | null,
  policy: GpuPolicy,
): { proceed: boolean; warning: string | null; gpuClass: GpuClass } {
  const gpuClass: GpuClass =
    vendor === "nvidia" || vendor === "amd"
      ? "discrete"
      : vendor === "intel"
        ? "integrated"
        : vendor === "apple"
          ? "unified"
          : "unknown";
  if (gpuClass === "discrete" || gpuClass === "unified")
    return { proceed: true, warning: null, gpuClass };
  const warning =
    gpuClass === "integrated"
      ? "integrated GPU: model weights live in shared system RAM; expect slower inference and higher RAM use"
      : "GPU class unknown (no WebGPU adapter info)";
  // Final policy is decided from iGPU measurements (DECISIONS D-023, provisional): until then "warn" lets the bench run.
  return { proceed: policy === "warn", warning, gpuClass };
}

export type LoadEvent = { t: number; text: string };
export type LoadPhases = {
  cold: boolean;
  download_ms: number;
  weights_load_ms: number;
  shader_ms: number;
  init_ms: number;
};

const phaseOf = (text: string, cold = false): "download" | "weights" | "shader" | "other" =>
  text.startsWith("Fetching param cache") || (cold && text.startsWith("Start to fetch params"))
    ? "download"
    : text.startsWith("Loading model from cache")
      ? "weights"
      : text.startsWith("Loading GPU shader modules")
        ? "shader"
        : "other";

/**
 * Split a WebLLM load into download / weights->GPU / shader compile / init using its progress messages.
 * Each interval between consecutive messages is attributed to the phase of the message that opened it;
 * time before the first message (wasm + model-lib setup) and after the last (graph/KV-cache setup) is "init".
 */
export function splitLoadPhases(events: LoadEvent[], totalMs: number): LoadPhases {
  const out = { download_ms: 0, weights_load_ms: 0, shader_ms: 0, init_ms: 0 };
  const first = events[0];
  if (!first) return { cold: false, ...out, init_ms: totalMs };
  const cold = events.some((e) => e.text.startsWith("Fetching param cache")); // a warm load never fetches
  out.init_ms += first.t;
  events.forEach((e, i) => {
    const end = events[i + 1]?.t ?? null;
    const phase = phaseOf(e.text, cold);
    if (end === null) {
      out.init_ms += totalMs - e.t;
      return;
    }
    const span = end - e.t;
    if (phase === "download") out.download_ms += span;
    else if (phase === "weights") out.weights_load_ms += span;
    else if (phase === "shader") out.shader_ms += span;
    else out.init_ms += span;
  });
  return { cold, ...out };
}

export const peakBytes = (samples: (number | null)[]): number | null => {
  const ok = samples.filter((x): x is number => typeof x === "number");
  return ok.length ? Math.max(...ok) : null;
};
