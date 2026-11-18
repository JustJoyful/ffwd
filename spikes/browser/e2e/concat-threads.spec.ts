import { readFileSync, writeFileSync } from "node:fs";
import { test } from "@playwright/test";

// Diagnostic for the one native-vs-wasm parity failure (eval/runtime_parity.py): a two-input concat re-encode hangs in
// ffmpeg.wasm even with `-threads 1`. Which extra thread caps (all harness-side) let it finish?
//   CONCAT_THREADS_OUT=<file.json> pnpm exec playwright test e2e/concat-threads.spec.ts
test("ffmpeg.wasm concat re-encode with filter thread caps", async ({ page }) => {
  test.skip(!process.env.CONCAT_THREADS_OUT, "set CONCAT_THREADS_OUT=<file.json>");
  test.setTimeout(900_000);
  const files = Object.fromEntries(
    ["clip_a.mp4", "clip_b.mp4"].map((f) => [
      f,
      readFileSync(`../../data/corpus/${f}`).toString("base64"),
    ]),
  );
  const enc = ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"];
  const cat = "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]";
  const variants: Record<string, string[]> = {
    // controls: is it two inputs, the concat filter, or the decoders' threads?
    two_inputs_no_filter: ["-i", "clip_a.mp4", "-i", "clip_b.mp4", "-map", "0:v:0", "-map", "1:a:0", ...enc, "-c:a", "aac"],
    concat_video_only: ["-i", "clip_a.mp4", "-i", "clip_b.mp4", "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", ...enc],
    concat_audio_only: ["-i", "clip_a.mp4", "-i", "clip_b.mp4", "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]", "-map", "[a]", "-c:a", "aac"],
    concat_av_output_threads_only: ["-i", "clip_a.mp4", "-i", "clip_b.mp4", "-filter_complex", cat, "-map", "[v]", "-map", "[a]", ...enc, "-c:a", "aac"],
    // hypothesis: decoder threads (input-side -threads) are what deadlocks
    concat_av_input_threads1: ["-threads", "1", "-i", "clip_a.mp4", "-threads", "1", "-i", "clip_b.mp4", "-filter_complex", cat, "-map", "[v]", "-map", "[a]", ...enc, "-c:a", "aac"],
  }; // prettier-ignore
  const rows: Record<string, unknown> = {};
  for (const [name, extra] of Object.entries(variants)) {
    await page.goto("/");
    rows[name] = await page.evaluate(
      async ({ files, extra }) => {
        type Spike = {
          loadFfmpeg(): Promise<any>; // eslint-disable-line @typescript-eslint/no-explicit-any
          execLogged(ff: any, a: string[], t?: number): Promise<{ code: number; log: string }>; // eslint-disable-line @typescript-eslint/no-explicit-any
          harnessArgs(a: string[], i: string, o: string): string[];
        };
        const sp = (window as unknown as { spike: Spike }).spike;
        const ff = await sp.loadFfmpeg();
        try {
          for (const [n, b64] of Object.entries(files))
            await ff.writeFile(
              n,
              Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)),
            );
          const args = [...extra, "{out:o}"];
          const t0 = performance.now();
          const stuck = new Promise<{ code: number; log: string }>((r) =>
            setTimeout(() => r({ code: -2, log: "hard timeout 40 s" }), 40_000),
          );
          const e = await Promise.race([
            sp.execLogged(ff, sp.harnessArgs(args, "x", "o.mp4"), 35_000),
            stuck,
          ]);
          return {
            code: e.code,
            seconds: Math.round((performance.now() - t0) / 100) / 10,
            tail: e.log.trim().split("\n").slice(-1)[0],
          };
        } finally {
          ff.terminate();
        }
      },
      { files, extra },
    );
    console.log(name, JSON.stringify(rows[name]));
  }
  writeFileSync(process.env.CONCAT_THREADS_OUT as string, JSON.stringify(rows, null, 2) + "\n");
});
