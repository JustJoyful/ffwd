import {
  CreateWebWorkerMLCEngine,
  hasModelInCache,
  prebuiltAppConfig,
  type MLCEngineInterface,
} from "@mlc-ai/web-llm";
import { record } from "./results";

async function storageUsage(): Promise<number> {
  return (await navigator.storage.estimate()).usage ?? 0;
}

/** Load one model and record download bytes (storage delta), load time and cache state. */
export async function loadModel(
  modelId: string,
  onProgress: (text: string) => void,
): Promise<MLCEngineInterface> {
  const inPrebuilt = prebuiltAppConfig.model_list.some((m) => m.model_id === modelId);
  const cached = await hasModelInCache(modelId).catch(() => false);
  const before = await storageUsage();
  const t0 = performance.now();
  const engine = await CreateWebWorkerMLCEngine(
    new Worker(new URL("./llm.worker.ts", import.meta.url), { type: "module" }),
    modelId,
    { initProgressCallback: (p) => onProgress(p.text) },
  );
  record({
    name: `webllm_load_${modelId}`,
    ok: true,
    ms: performance.now() - t0,
    detail: { inPrebuilt, warm: cached, downloadedBytesApprox: (await storageUsage()) - before },
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

/** Refuse to run on the wrong GPU: on this hybrid laptop an iGPU fallback puts weights in system RAM. */
export async function requireDiscreteGpu(): Promise<void> {
  const nav = navigator as Navigator & {
    gpu?: {
      requestAdapter(o: {
        powerPreference: string;
      }): Promise<{ info?: { vendor?: string } } | null>;
    };
  };
  const a = await nav.gpu?.requestAdapter({ powerPreference: "high-performance" });
  const vendor = a?.info?.vendor ?? "none";
  record({
    name: "webgpu_adapter",
    ok: vendor === "nvidia",
    detail: { vendor, preference: "high-performance" },
  });
  if (vendor !== "nvidia")
    throw new Error(`high-performance WebGPU adapter is '${vendor}', not the discrete GPU`);
}
