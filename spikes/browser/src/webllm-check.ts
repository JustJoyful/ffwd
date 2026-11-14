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
