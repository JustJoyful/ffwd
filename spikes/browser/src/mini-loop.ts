// Minimal in-browser agent loop for the Phase 0 exit criterion: F1/F4/F7 must RUN end to end
// (model → validated run → ffmpeg.wasm → check). Pass/fail of the base model is recorded as it is.
import type { FFmpeg } from "@ffmpeg/ffmpeg";
import { fetchFile } from "@ffmpeg/util";
import type { ChatCompletionMessageParam, MLCEngineInterface } from "@mlc-ai/web-llm";
import systemPrompt from "../../../packages/protocol/prompts/system-v0.txt?raw";
import { parseAction } from "./actions";
import { FRAME_COUNT_TOLERANCE, MAX_RUNS, MAX_TOKENS, MAX_TURNS, TIME_TOLERANCE_S } from "./config";
import { capThreads, execLogged, outputBytes, substitute } from "./ffmpeg-check";
import { parseFfmpegDuration, parseVideoSize, record, type CheckRecord } from "./results";
import { validateRun } from "./validator";

type Family = "F1" | "F4" | "F7";

async function probeLite(ff: FFmpeg, name: string) {
  const { log } = await execLogged(ff, ["-hide_banner", "-i", name]); // exits 1 (no output) but logs the probe
  const size = parseVideoSize(log);
  return {
    duration_s: parseFfmpegDuration(log),
    width: size?.[0] ?? null,
    height: size?.[1] ?? null,
  };
}

async function miniCheck(
  ff: FFmpeg,
  family: Family,
  outName: string,
  inDuration: number,
): Promise<{ passed: boolean; detail: unknown }> {
  if (family === "F7") {
    const count = await outputBytes(ff, outName);
    const expected = Math.floor(inDuration / 2);
    return {
      passed: Math.abs(count - expected) <= FRAME_COUNT_TOLERANCE,
      detail: { count, expected },
    };
  }
  const p = await probeLite(ff, outName);
  if (family === "F1") {
    const expected = inDuration - 3;
    return {
      passed: p.duration_s !== null && Math.abs(p.duration_s - expected) <= TIME_TOLERANCE_S,
      detail: { duration: p.duration_s, expected },
    };
  }
  return { passed: p.height === 480, detail: { height: p.height, expected: 480 } };
}

export async function runMiniLoop(
  task: { family: Family; request: string },
  file: File,
  engine: MLCEngineInterface,
  ff: FFmpeg,
  modelId: string,
): Promise<CheckRecord> {
  await ff.writeFile("loop_in.mp4", await fetchFile(file));
  const inProbe = await probeLite(ff, "loop_in.mp4");
  const outName = task.family === "F7" ? "loop_frames/%04d.png" : "loop_out.mp4";
  const messages: ChatCompletionMessageParam[] = [
    { role: "system", content: systemPrompt },
    {
      role: "user",
      content: JSON.stringify({
        request: task.request,
        inputs: [{ id: "clip", probe: inProbe }],
        outputs: ["out1"],
      }),
    },
  ];
  let runs = 0,
    invalid = 0,
    passed = false,
    ended = "turn_budget";
  const t0 = performance.now();
  for (let turn = 0; turn < MAX_TURNS && ended === "turn_budget"; turn++) {
    const reply = await engine.chat.completions.create({
      messages,
      temperature: 0,
      max_tokens: MAX_TOKENS,
      extra_body: { enable_thinking: false }, // Qwen3 non-thinking [VERIFY in pinned WebLLM]
    });
    const text = reply.choices[0]?.message.content ?? "";
    const action = parseAction(text);
    let obs: unknown;
    if ("error" in action) {
      invalid++;
      obs = { error: action.error };
    } else if (action.action === "run") {
      const v = validateRun(action.args, action.inputs, action.outputs, {
        inputs: new Set(["clip"]),
        outputs: new Set(["out1"]),
      });
      if (!v.ok) {
        obs = { run_ok: false, rejected: v.reason };
      } else {
        runs++;
        if (task.family === "F7") await ff.createDir("loop_frames").catch(() => undefined);
        const r = await execLogged(ff, substitute(capThreads(action.args), "loop_in.mp4", outName));
        const c =
          r.code === 0 ? await miniCheck(ff, task.family, outName, inProbe.duration_s ?? 0) : null;
        passed = c?.passed ?? false;
        obs =
          r.code === 0
            ? { run_ok: true, check: c }
            : { run_ok: false, stderr_tail: r.log.slice(-1500) };
        if (runs >= MAX_RUNS && !passed) ended = "run_budget";
      }
    } else if (action.action === "finish") {
      if (passed) ended = "finish";
      else obs = { error: "finish requires a passing check" };
    } else if (action.action === "unsupported") {
      ended = "unsupported";
    } else {
      obs =
        action.action === "spec"
          ? { spec: "confirmed" }
          : { answer: "No more information is available; proceed with your best interpretation." };
    }
    messages.push(
      { role: "assistant", content: text },
      { role: "user", content: JSON.stringify(obs ?? { ended }) },
    );
  }
  const rec: CheckRecord = {
    name: `mini_loop_${task.family}_${modelId}`,
    ok: true, // the loop RAN end to end; model success is reported separately
    ms: performance.now() - t0,
    detail: { modelPassed: passed, runs, invalidTurns: invalid, ended },
  };
  record(rec);
  return rec;
}
