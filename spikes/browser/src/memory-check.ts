import { record } from "./results";

type MemoryApi = { measureUserAgentSpecificMemory?: () => Promise<{ bytes: number }> };

/** Tab memory via the cross-origin-isolated-only API (Chrome/Edge); falls back to JS heap size. */
export async function recordMemory(label: string): Promise<void> {
  const perf = performance as Performance & MemoryApi & { memory?: { usedJSHeapSize: number } };
  try {
    if (perf.measureUserAgentSpecificMemory) {
      const m = await perf.measureUserAgentSpecificMemory();
      record({
        name: `memory_${label}`,
        ok: true,
        detail: { bytes: m.bytes, api: "measureUserAgentSpecificMemory" },
      });
      return;
    }
  } catch (e) {
    record({ name: `memory_${label}`, ok: false, detail: { error: String(e) } });
    return;
  }
  record({
    name: `memory_${label}`,
    ok: Boolean(perf.memory),
    detail: {
      bytes: perf.memory?.usedJSHeapSize ?? null,
      api: "performance.memory (JS heap only)",
    },
  });
}
