// Collected measurements, downloadable as JSON into reports/<date>-phase-0/browser/.
export type CheckRecord = {
  name: string;
  ok: boolean;
  ms?: number;
  detail?: Record<string, unknown>;
};

const records: CheckRecord[] = [];
const listeners: ((r: CheckRecord) => void)[] = [];

const STORE = "ffagent-bench-records";

// Records are mirrored to localStorage so a tab crash (the 500 MB input test can kill the tab) keeps everything
// measured so far; restoreSaved() reloads them after the page is reopened.
function persist(): void {
  try {
    localStorage.setItem(STORE, JSON.stringify(records));
  } catch {
    /* storage unavailable or full: measurements just aren't crash-safe */
  }
}

export function record(r: CheckRecord): void {
  records.push(r);
  persist();
  listeners.forEach((l) => l(r));
}

export function restoreSaved(): CheckRecord[] {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE) ?? "[]") as CheckRecord[];
    saved.forEach((r) => records.push(r));
    return saved;
  } catch {
    return [];
  }
}

export function clearSaved(): void {
  records.length = 0;
  try {
    localStorage.removeItem(STORE);
  } catch {
    /* ignore */
  }
}

export function onRecord(l: (r: CheckRecord) => void): void {
  listeners.push(l);
}

export async function environment(): Promise<Record<string, unknown>> {
  const nav = navigator as Navigator & {
    deviceMemory?: number;
    gpu?: { requestAdapter(): Promise<{ info?: unknown } | null> };
  };
  const adapter = nav.gpu ? await nav.gpu.requestAdapter().catch(() => null) : null;
  return {
    userAgent: nav.userAgent,
    hardwareConcurrency: nav.hardwareConcurrency,
    deviceMemoryGb: nav.deviceMemory ?? null,
    webgpu: Boolean(nav.gpu),
    gpuAdapter: adapter?.info ?? null,
    crossOriginIsolated: self.crossOriginIsolated,
  };
}

export async function downloadResults(machineLabel: string): Promise<void> {
  const body = JSON.stringify(
    { machine: machineLabel, date: new Date().toISOString(), env: await environment(), records },
    null,
    2,
  );
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([body], { type: "application/json" }));
  a.download = `phase0-browser-${machineLabel.replace(/[^a-z0-9-]/gi, "_")}.json`;
  a.click();
}

export function parseFfmpegDuration(log: string): number | null {
  const m = /Duration: (\d+):(\d{2}):(\d{2}(?:\.\d+)?)/.exec(log);
  return m ? Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]) : null;
}

export function parseVideoSize(log: string): [number, number] | null {
  const sizes = [...log.matchAll(/Stream #\d+:\d+.*?: Video: .*?(\d{2,5})x(\d{2,5})/g)];
  const last = sizes.at(-1);
  return last ? [Number(last[1]), Number(last[2])] : null;
}

export function parseFrameCount(log: string): number | null {
  const frames = [...log.matchAll(/frame=\s*(\d+)/g)];
  const last = frames.at(-1);
  return last ? Number(last[1]) : null;
}
