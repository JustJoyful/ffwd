import type { FFmpeg } from "@ffmpeg/ffmpeg";
import { MINI_LOOP_TASKS, MODEL_IDS } from "./config";
import { execLogged, loadFfmpeg, runFfmpegChecks } from "./ffmpeg-check";
import { recordMemory } from "./memory-check";
import { runMiniLoop } from "./mini-loop";
import { downloadResults, onRecord, record } from "./results";
import { loadModel, measureSpeed } from "./webllm-check";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const file = (id: string) => $<HTMLInputElement>(id).files?.[0] ?? null;
const status = (t: string) => ($("status").textContent = t);

onRecord((r) => {
  const li = document.createElement("li");
  li.textContent = `${r.ok ? "✓" : "✗"} ${r.name}${r.ms !== undefined ? ` (${Math.round(r.ms)} ms)` : ""} ${r.detail ? JSON.stringify(r.detail) : ""}`;
  $("log").append(li);
});

let ff: FFmpeg | null = null;
const ensureFfmpeg = async () => (ff ??= await loadFfmpeg());

async function guarded(label: string, fn: () => Promise<void>): Promise<void> {
  status(`${label}…`);
  try {
    await fn();
    status(`${label}: done`);
  } catch (e) {
    record({ name: `${label}_error`, ok: false, detail: { error: String(e) } });
    status(`${label}: failed (${String(e)})`);
  }
}

$("isolated").textContent = String(self.crossOriginIsolated);
$("run-ffmpeg").onclick = () =>
  guarded("ffmpeg checks", async () =>
    runFfmpegChecks(await ensureFfmpeg(), file("hevc-file"), file("long-file")),
  );
$("run-model").onclick = () =>
  guarded("model checks", async () => {
    const modelId = $<HTMLSelectElement>("model").value;
    const engine = await loadModel(modelId, status);
    await recordMemory(`after_load_${modelId}`);
    await measureSpeed(engine, modelId);
    const long = file("long-file");
    if (long)
      for (const t of MINI_LOOP_TASKS)
        await runMiniLoop(t, long, engine, await ensureFfmpeg(), modelId);
    await recordMemory(`after_loop_${modelId}`);
  });
$("run-memory").onclick = () =>
  guarded("memory test", async () => {
    const big = file("big-file");
    if (!big) throw new Error("pick a large file first");
    const f = await ensureFfmpeg();
    await recordMemory(`before_${big.size}`);
    await f.writeFile("big.mp4", new Uint8Array(await big.arrayBuffer()));
    const r = await execLogged(f, [
      "-i",
      "big.mp4",
      "-vf",
      "scale=-2:480",
      "-c:v",
      "libx264",
      "-preset",
      "ultrafast",
      "-c:a",
      "copy",
      "big_out.mp4",
    ]);
    await recordMemory(`after_${big.size}`);
    record({
      name: `big_file_${big.size}`,
      ok: r.code === 0,
      ms: r.ms,
      detail: { inputBytes: big.size },
    });
    await f.deleteFile("big.mp4").catch(() => undefined);
    await f.deleteFile("big_out.mp4").catch(() => undefined);
  });
$("download").onclick = () => downloadResults($<HTMLInputElement>("machine").value || "unlabelled");
for (const id of MODEL_IDS) $("model").append(new Option(id, id));
