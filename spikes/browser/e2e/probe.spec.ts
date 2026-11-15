import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { expect, test } from "@playwright/test";

const dir = "../../data/corpus";
const clips = readdirSync(dir).filter((x) => /\.(mp4|mov|webm|avi)$/.test(x));

// Measures the two ways to probe in ffmpeg.wasm and, for each, whether a REAL command still runs afterwards.
// PROBE_MEASURE_OUT=<file.json> saves the numbers (reports/2026-11-16-phase0-followups/browser-probe-measure.json).
test("probe strategies: ffmpeg -i parse vs ffprobe(+core reload); nothing poisons later commands", async ({
  page,
}) => {
  test.skip(clips.length === 0, "generate the corpus first");
  test.setTimeout(240_000);
  await page.goto("/");
  const files = Object.fromEntries(
    clips.map((f) => [f, readFileSync(`${dir}/${f}`).toString("base64")]),
  );
  const result = await page.evaluate(async (files) => {
    type Spike = {
      ensureFfmpeg(): Promise<any>; // eslint-disable-line @typescript-eslint/no-explicit-any
      loadFfmpeg(): Promise<any>; // eslint-disable-line @typescript-eslint/no-explicit-any
      execLogged(ff: any, a: string[]): Promise<{ code: number; log: string; ms: number }>; // eslint-disable-line @typescript-eslint/no-explicit-any
      probeViaLog(ff: any, n: string): Promise<{ duration_s: number | null }>; // eslint-disable-line @typescript-eslint/no-explicit-any
      ffprobeJson(ff: any, n: string): Promise<string>; // eslint-disable-line @typescript-eslint/no-explicit-any
      harnessArgs(a: string[], i: string, o: string): string[];
    };
    const sp = (window as unknown as { spike: Spike }).spike;
    const bytes = (b64: string) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const trim = (i: string, o: string) =>
      sp.harnessArgs(["-i", "{in:c}", "-t", "1", "-c", "copy", "{out:o}"], i, o);
    const rows: Record<string, unknown>[] = [];
    const attempt = async <T>(f: () => Promise<T>): Promise<T | string> => {
      try {
        return await f();
      } catch (e) {
        return `threw: ${String(e).slice(0, 70)}`;
      }
    };
    for (const [name, b64] of Object.entries(files)) {
      // Each strategy gets its own fresh core so one cannot hide the other's side effects.
      let t = performance.now();
      const ffA = await sp.loadFfmpeg();
      const loadMs = performance.now() - t;
      await ffA.writeFile(name, bytes(b64));
      // A) ffmpeg -i parse, then a real command, then probe again
      t = performance.now();
      const pa = await attempt(() => sp.probeViaLog(ffA, name));
      const logMs = performance.now() - t;
      const afterLog = await attempt(
        async () => (await sp.execLogged(ffA, trim(name, "a_out.mp4"))).code,
      );
      const logAgain = await attempt(async () => (await sp.probeViaLog(ffA, name)).duration_s);
      ffA.terminate();
      // B) ffprobe JSON, then a real command, then ffmpeg -i again, on the same instance
      const ffB = await sp.loadFfmpeg();
      await ffB.writeFile(name, bytes(b64));
      t = performance.now();
      const fj = await attempt(() => sp.ffprobeJson(ffB, name));
      const ffprobeMs = performance.now() - t;
      const afterFfprobe = await attempt(
        async () => (await sp.execLogged(ffB, trim(name, "b_out.mp4"))).code,
      );
      const logAfterFfprobe = await attempt(
        async () => (await sp.probeViaLog(ffB, name)).duration_s,
      );
      ffB.terminate();
      rows.push({
        clip: name,
        coreLoadMs: Math.round(loadMs),
        logProbeMs: Math.round(logMs),
        logProbeDuration: typeof pa === "string" ? pa : pa.duration_s,
        execAfterLogProbeExit: afterLog,
        logProbeAgainDuration: logAgain,
        ffprobeMs: Math.round(ffprobeMs),
        ffprobeJsonBytes: fj.startsWith("threw:") ? fj : fj.length,
        execAfterFfprobeExit: afterFfprobe,
        logProbeAfterFfprobeDuration: logAfterFfprobe,
      });
    }
    return rows;
  }, files);
  const med = (k: string) =>
    [...result.map((r) => r[k] as number)].sort((a, b) => a - b)[Math.floor(result.length / 2)];
  const summary = {
    clips: result.length,
    medianMs: {
      logProbe: med("logProbeMs"),
      ffprobe: med("ffprobeMs"),
      coreReload: med("coreLoadMs"),
    },
  };
  console.log(
    JSON.stringify(summary),
    JSON.stringify(
      result.map((r) => [
        r.clip,
        r.execAfterLogProbeExit,
        r.logProbeAgainDuration,
        r.ffprobeJsonBytes,
        r.execAfterFfprobeExit,
        r.logProbeAfterFfprobeDuration,
      ]),
    ),
  );
  if (process.env.PROBE_MEASURE_OUT) {
    mkdirSync(dirname(process.env.PROBE_MEASURE_OUT), { recursive: true });
    writeFileSync(
      process.env.PROBE_MEASURE_OUT,
      JSON.stringify(
        { date: new Date().toISOString(), core: "@ffmpeg/core-mt 0.12.10", summary, rows: result },
        null,
        2,
      ),
    );
  }
  // The decision rule: the chosen strategy must never break the command that follows it.
  for (const r of result) {
    expect(r.execAfterLogProbeExit, `${r.clip}: command after ffmpeg -i probe`).toBe(0);
    expect(typeof r.logProbeAgainDuration, `${r.clip}: second ffmpeg -i probe`).toBe("number");
  }
});
