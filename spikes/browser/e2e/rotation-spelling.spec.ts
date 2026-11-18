import { readFileSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

// Which lossless-rotation spelling works in ffmpeg.wasm, and what display-matrix angle does each rotate=N give?
// ROTATION_SPELLING_OUT=<file.json> saves the result (compare with the native run in the same report directory).
test("ffmpeg.wasm lossless rotation spellings", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/");
  const b64 = readFileSync("../../data/corpus/h264_aac_1080p.mp4").toString("base64");
  const result = await page.evaluate(async (b64) => {
    type Exec = { code: number; log: string; ms: number };
    type Spike = {
      loadFfmpeg(): Promise<any>; // eslint-disable-line @typescript-eslint/no-explicit-any
      execLogged(ff: any, a: string[]): Promise<Exec>; // eslint-disable-line @typescript-eslint/no-explicit-any
      harnessArgs(a: string[], i: string, o: string): string[];
    };
    const sp = (window as unknown as { spike: Spike }).spike;
    const ff = await sp.loadFfmpeg();
    await ff.writeFile(
      "in.mp4",
      Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)),
    );
    const version = (await sp.execLogged(ff, ["-version"])).log.split("\n")[0];
    const cases: Record<string, string[]> = {
      display_rotation_90: ["-display_rotation", "90", "-i", "{in:c}", "-c", "copy", "{out:o}"],
    };
    for (const n of [0, 90, 180, 270])
      cases[`rotate_${n}`] = [
        "-i",
        "{in:c}",
        "-c",
        "copy",
        "-metadata:s:v:0",
        `rotate=${n}`,
        "{out:o}",
      ];
    const rows: Record<string, unknown> = {};
    for (const [name, args] of Object.entries(cases)) {
      const out = `${name}.mp4`;
      const r = await sp.execLogged(ff, sp.harnessArgs(args, "in.mp4", out));
      const probe = r.code === 0 ? (await sp.execLogged(ff, ["-i", out])).log : "";
      rows[name] = {
        exit_code: r.code,
        error_tail: r.code === 0 ? null : r.log.trim().split("\n").slice(-2).join(" | "),
        displaymatrix_ccw: /displaymatrix: rotation of (-?[\d.]+) degrees/.exec(probe)?.[1] ?? null,
        size: /Stream #0:0.*?, (\d+x\d+)/.exec(probe)?.[1] ?? null,
      };
    }
    ff.terminate();
    return { version, rows };
  }, b64);
  if (process.env.ROTATION_SPELLING_OUT)
    writeFileSync(process.env.ROTATION_SPELLING_OUT, JSON.stringify(result, null, 2) + "\n");
  console.log(JSON.stringify(result, null, 2));
  expect(result.version).toContain("ffmpeg version");
});
