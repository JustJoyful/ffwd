import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { test } from "@playwright/test";

// Runs every recipe in cases.json (written by `python -m eval.runtime_parity`) inside ffmpeg.wasm, through the same argument
// rewriting the browser uses for model actions (harnessArgs: thread cap), and saves each output under PARITY_OUT/<i>/.
// The checker verdicts are computed by eval/parity.py on those files; this spec only runs FFmpeg.
type Case = {
  i: number;
  name: string;
  inputs: Record<string, string>;
  args: string[];
  out: string;
};
const CASES = process.env.PARITY_CASES;
const OUT = process.env.PARITY_OUT;

test("run every conformance recipe in ffmpeg.wasm", async ({ page }) => {
  test.skip(
    !CASES || !OUT,
    "run through `python -m eval.runtime_parity` (sets PARITY_CASES and PARITY_OUT)",
  );
  test.setTimeout(3_600_000);
  const cases: Case[] = JSON.parse(readFileSync(CASES as string, "utf8"));
  await page.goto("/");
  const rows: Record<string, unknown>[] = [];
  for (const c of cases) {
    const inputs = Object.fromEntries(
      Object.entries(c.inputs).map(([id, f]) => [
        id,
        readFileSync(`../../data/corpus/${f}`).toString("base64"),
      ]),
    );
    const r = await page.evaluate(
      async ({ c, inputs }) => {
        type Spike = {
          loadFfmpeg(): Promise<any>; // eslint-disable-line @typescript-eslint/no-explicit-any
          execLogged(ff: any, a: string[], t?: number): Promise<{ code: number; log: string }>; // eslint-disable-line @typescript-eslint/no-explicit-any
          harnessArgs(a: string[], i: string, o: string): string[];
        };
        const sp = (window as unknown as { spike: Spike }).spike;
        const b64 = (u: Uint8Array) => {
          let s = "";
          for (let k = 0; k < u.length; k += 0x8000)
            s += String.fromCharCode(...u.subarray(k, k + 0x8000));
          return btoa(s);
        };
        const ff = await sp.loadFfmpeg();
        try {
          const names: Record<string, string> = {};
          for (const [id, data] of Object.entries(inputs)) {
            names[id] = c.inputs[id] as string;
            await ff.writeFile(
              names[id],
              Uint8Array.from(atob(data), (x) => x.charCodeAt(0)),
            );
          }
          if (c.out.includes("/")) await ff.createDir(c.out.split("/")[0]);
          const args = c.args.map((a) => {
            const m = /^\{in:(.+)\}$/.exec(a);
            return m ? (names[m[1] as string] as string) : a;
          });
          // Hard stop: a wasm re-encode can deadlock and ffmpeg.wasm's own timeout then never settles.
          const stuck = new Promise<{ code: number; log: string }>((res) =>
            setTimeout(
              () => res({ code: -2, log: "hard timeout: ffmpeg.wasm did not finish in 150 s" }),
              150_000,
            ),
          );
          const e = await Promise.race([
            sp.execLogged(ff, sp.harnessArgs(args, "unused", c.out), 120_000),
            stuck,
          ]);
          const files: Record<string, string> = {};
          if (e.code === 0) {
            if (c.out.includes("/")) {
              const dir = c.out.split("/")[0] as string;
              for (const f of (await ff.listDir(dir)) as { name: string; isDir: boolean }[])
                if (!f.isDir)
                  files[`${dir}/${f.name}`] = b64(
                    (await ff.readFile(`${dir}/${f.name}`)) as Uint8Array,
                  );
            } else files[c.out] = b64((await ff.readFile(c.out)) as Uint8Array);
          }
          return { code: e.code, log_tail: e.log.trim().split("\n").slice(-3).join(" | "), files };
        } catch (err) {
          return { code: -1, log_tail: `threw: ${String(err).slice(0, 200)}`, files: {} };
        } finally {
          ff.terminate();
        }
      },
      { c, inputs },
    );
    if (r.code === -2) await page.goto("/"); // a deadlocked core may poison the page: start the next case clean
    for (const [name, data] of Object.entries(r.files)) {
      const p = `${OUT}/${c.i}/${name}`;
      mkdirSync(p.substring(0, p.lastIndexOf("/")), { recursive: true });
      writeFileSync(p, Buffer.from(data, "base64"));
    }
    rows.push({
      i: c.i,
      name: c.name,
      code: r.code,
      log_tail: r.log_tail,
      outputs: Object.keys(r.files),
    });
    console.log(`case ${c.i} exit ${r.code}: ${c.name}`);
  }
  writeFileSync(`${OUT}/results.json`, JSON.stringify(rows, null, 2) + "\n");
});
