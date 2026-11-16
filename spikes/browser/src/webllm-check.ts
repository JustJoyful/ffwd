import {
  CreateWebWorkerMLCEngine,
  deleteModelAllInfoInCache,
  hasModelInCache,
  prebuiltAppConfig,
  type MLCEngineInterface,
} from "@mlc-ai/web-llm";
import { gpuDecision, splitLoadPhases, type LoadEvent } from "./bench-core";
import type { GpuPolicy } from "./config";
import { record } from "./results";

async function storageUsage(): Promise<number> {
  return (await navigator.storage.estimate()).usage ?? 0;
}

/**
 * Load one model and record load time, cache state and the download / weights / shader / init split
 * (from WebLLM's own progress messages). forceCold clears the cached model first so the download is measured.
 */
export async function loadModel(
  modelId: string,
  onProgress: (text: string) => void,
  opts: { forceCold?: boolean; label?: string } = {},
): Promise<MLCEngineInterface> {
  const inPrebuilt = prebuiltAppConfig.model_list.some((m) => m.model_id === modelId);
  if (opts.forceCold) await deleteModelAllInfoInCache(modelId).catch(() => undefined);
  const cached = await hasModelInCache(modelId).catch(() => false);
  const before = await storageUsage();
  const t0 = performance.now();
  const events: LoadEvent[] = [];
  const engine = await CreateWebWorkerMLCEngine(
    new Worker(new URL("./llm.worker.ts", import.meta.url), { type: "module" }),
    modelId,
    {
      initProgressCallback: (p) => {
        events.push({ t: performance.now() - t0, text: p.text });
        onProgress(p.text);
      },
    },
  );
  const total = performance.now() - t0;
  record({
    name: `webllm_load_${modelId}${opts.label ? `_${opts.label}` : ""}`,
    ok: true,
    ms: total,
    detail: {
      inPrebuilt,
      warm: cached,
      downloadedBytesApprox: (await storageUsage()) - before,
      phases: splitLoadPhases(events, total),
    },
  });
  return engine;
}

/** Decode speed from WebLLM's own runtime stats after a short fixed generation. */
export async function measureSpeed(engine: MLCEngineInterface, modelId: string): Promise<void> {
  await engine.chat.completions.create({
    messages: [{ role: "user", content: "List the numbers from 1 to 40 separated by commas." }],
    temperature: 0,
    max_tokens: 128,
  });
  const stats = await engine.runtimeStatsText();
  const num = (k: string) => Number(new RegExp(`${k}: ([\\d.]+) tok/s`).exec(stats)?.[1] ?? NaN);
  record({
    name: `webllm_speed_${modelId}`,
    ok: true,
    detail: { prefillTokPerS: num("prefill"), decodeTokPerS: num("decode"), stats },
  });
}

/** Is Qwen3 really in non-thinking mode? Without it llama.cpp spent all tokens in reasoning and returned empty content. */
export async function checkThinking(engine: MLCEngineInterface, modelId: string): Promise<void> {
  const r = await engine.chat.completions.create({
    messages: [{ role: "user", content: 'Reply with exactly {"ok": true}' }],
    temperature: 0,
    max_tokens: 200,
    extra_body: { enable_thinking: false },
  });
  const content = r.choices[0]?.message.content ?? "";
  // Non-thinking Qwen3 still emits an EMPTY <think></think> block; only real reasoning text (or no answer) is a failure.
  const answer = content.replace(/<think>\s*<\/think>/g, "").trim();
  const thinking = /<think>/.test(answer) || answer === "";
  record({
    name: `webllm_thinking_off_${modelId}`,
    ok: !thinking,
    detail: { content: content.slice(0, 200), completionTokens: r.usage?.completion_tokens },
  });
}

type AdapterInfo = {
  vendor?: string;
  architecture?: string;
  device?: string;
  description?: string;
};
type GpuAdapter = {
  info?: AdapterInfo;
  isFallbackAdapter?: boolean;
  limits?: { maxBufferSize?: number };
};

/**
 * Record both WebGPU adapters (high-performance and low-power) and apply the discrete-GPU policy.
 * On a hybrid laptop these are different GPUs; on an iGPU-only machine they are the same one.
 * Throws only if the policy is "refuse" and the high-performance adapter is not a discrete GPU.
 */
export async function checkGpu(policy: GpuPolicy) {
  const nav = navigator as Navigator & {
    gpu?: { requestAdapter(o: { powerPreference: string }): Promise<GpuAdapter | null> };
  };
  const seen: Record<string, unknown> = {};
  let vendor: string | null = null;
  for (const preference of ["high-performance", "low-power"]) {
    const a =
      (await nav.gpu?.requestAdapter({ powerPreference: preference }).catch(() => null)) ?? null;
    seen[preference] = a
      ? {
          ...a.info,
          isFallbackAdapter: a.isFallbackAdapter ?? null,
          maxBufferSize: a.limits?.maxBufferSize ?? null,
        }
      : null;
    if (preference === "high-performance") vendor = a?.info?.vendor ?? null;
  }
  const decision = gpuDecision(vendor, policy);
  record({
    name: "webgpu_adapter",
    ok: decision.proceed && decision.warning === null,
    detail: { policy, ...decision, adapters: seen },
  });
  if (!decision.proceed) {
    throw new Error(
      `GPU policy 'refuse': high-performance adapter is '${vendor ?? "none"}' (${decision.gpuClass})`,
    );
  }
  return decision;
}
