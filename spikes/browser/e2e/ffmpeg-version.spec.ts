import { readFileSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

// Which FFmpeg is inside ffmpeg.wasm, and which lossless/lossy rotation methods does it support?
// FFMPEG_VERSION_OUT=<file.json> saves the result (reports/2026-11-16-spike-v1/wasm-ffmpeg-capabilities.json).
test("ffmpeg.wasm version and rotation capabilities", async ({ page }) => {
  test.setTimeout(120_000);
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
    const candidates: Record<string, string[]> = {
      display_rotation_90: ["-display_rotation", "90", "-i", "{in:c}", "-c", "copy", "{out:o}"],
      metadata_rotate_90: ["-i", "{in:c}", "-c", "copy", "-metadata:s:v:0", "rotate=90", "{out:o}"],
      transpose_1_reencode: ["-i", "{in:c}", "-vf", "transpose=1", "-c:a", "copy", "{out:o}"],
    };
    const rows: Record<string, unknown> = {};
    for (const [name, args] of Object.entries(candidates)) {
      const out = `${name}.mp4`;
      const r = await sp.execLogged(ff, sp.harnessArgs(args, "in.mp4", out));
      const probe = r.code === 0 ? (await sp.execLogged(ff, ["-i", out])).log : "";
      rows[name] = {
        exit_code: r.code,
        error_tail: r.code === 0 ? null : r.log.trim().split("\n").slice(-2).join(" | "),
        displaymatrix: /displaymatrix: rotation of (-?[\d.]+) degrees/.exec(probe)?.[1] ?? null,
        size: /Stream #0:0.*?, (\d+x\d+)/.exec(probe)?.[1] ?? null,
      };
    }
    // Frame-count boundary (checker counting rule): 4 s clip, one frame per 3 s. FFmpeg 9.0.2 gives 1 with the fps
    // filter and 2 with select; what does 5.1.4 give?
    const frames: Record<string, number> = {};
    for (const [name, vf] of Object.entries({
      fps_1_3: "fps=1/3",
      select_3: "select='isnan(prev_selected_t)+gte(t-prev_selected_t,3)'",
    })) {
      await sp.execLogged(
        ff,
        sp.harnessArgs(
          ["-i", "{in:c}", "-vf", vf, "-fps_mode", "vfr", "{out:o}"],
          "in.mp4",
          `${name}_%03d.png`,
        ),
      );
      const listing = (await ff.listDir(".")) as { name: string }[];
      frames[name] = listing.filter((f) => f.name.startsWith(`${name}_`)).length;
    }
    ff.terminate();
    return { version, rows, frames };
  }, b64);
  if (process.env.FFMPEG_VERSION_OUT)
    writeFileSync(process.env.FFMPEG_VERSION_OUT, JSON.stringify(result, null, 2) + "\n");
  console.log(JSON.stringify(result, null, 2));
  expect(result.version).toContain("ffmpeg version");
});
