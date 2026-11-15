// Minimal in-browser agent loop for the Phase 0 exit criterion: F1/F4/F7 must RUN end to end
// (model → validated run → ffmpeg.wasm → check). Pass/fail of the base model is recorded as it is.
import type { FFmpeg } from "@ffmpeg/ffmpeg";
import { fetchFile } from "@ffmpeg/util";
import type { ChatCompletionMessageParam, MLCEngineInterface } from "@mlc-ai/web-llm";
import systemPrompt from "../../../packages/protocol/prompts/system-v0.txt?raw";
import { parseAction } from "./actions";
import { FRAME_COUNT_TOLERANCE, MAX_RUNS, MAX_TOKENS, MAX_TURNS, TIME_TOLERANCE_S } from "./config";
import { runValidated } from "./executor";
import { outputBytes } from "./ffmpeg-check";
import { probeViaLog } from "./probe";
import { record, type CheckRecord } from "./results";

type Family = "F1" | "F4" | "F7";

/** One model turn: messages in, raw reply text out. The loop is identical for a real model and a script. */
export type Chat = (messages: ChatCompletionMessageParam[]) => Promise<string>;

// Minimal grammar for WebLLM's json_object mode: it needs a schema string. Full validation stays in
// the loop (parseAction + validateRun); this only forces "a JSON object with an action field".
const ACTION_SCHEMA = JSON.stringify({
  type: "object",
  properties: { action: { enum: ["spec", "ask_user", "unsupported", "run", "finish"] } },
  required: ["action"],
});

/** WebLLM engine as a Chat. json=true adds response_format json_object (ARCH §4: constrained output). */
export function engineChat(engine: MLCEngineInterface, json: boolean): Chat {
  return async (messages) => {
    const reply = await engine.chat.completions.create({
      messages,
      temperature: 0,
      max_tokens: MAX_TOKENS,
      extra_body: { enable_thinking: false }, // Qwen3 non-thinking; verified by checkThinking()
      ...(json ? { response_format: { type: "json_object" as const, schema: ACTION_SCHEMA } } : {}),
    });
    return reply.choices[0]?.message.content ?? "";
  };
}

/**
 * Plumbing proof: the reference solution for each family, fed through the exact same
 * parseAction → runValidated (validate + harness cap) → ffmpeg.exec → check path. Proves the browser loop works
 * independently of how good the base model is.
 */
export function scriptedChat(family: Family): Chat {
  const args: Record<Family, string[]> = {
    F1: ["-ss", "3", "-i", "{in:clip}", "-c", "copy", "{out:out1}"],
    F4: [
      "-i",
      "{in:clip}",
      "-vf",
      "scale=-2:480",
      "-c:v",
      "libx264",
      "-preset",
      "veryfast",
      "{out:out1}",
    ],
    F7: ["-i", "{in:clip}", "-vf", "fps=1/2", "{out:out1}"],
  };
  const replies = [
    JSON.stringify({
      action: "spec",
      spec: { family: [family], outputs: [{ id: "out1", kind: "video" }] },
    }),
    JSON.stringify({ action: "run", args: args[family], inputs: ["clip"], outputs: ["out1"] }),
    JSON.stringify({ action: "finish", outputs: ["out1"], note: "scripted" }),
  ];
  return async () => replies.shift() ?? "{}";
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
  const p = await probeViaLog(ff, outName);
  const height = p.streams.find((x) => x.type === "video")?.height ?? null;
  if (family === "F1") {
    const expected = inDuration - 3;
    return {
      passed: p.duration_s !== null && Math.abs(p.duration_s - expected) <= TIME_TOLERANCE_S,
      detail: { duration: p.duration_s, expected },
    };
  }
  return { passed: height === 480, detail: { height, expected: 480 } };
}

export async function runMiniLoop(
  task: { family: Family; request: string },
  file: File,
  chat: Chat,
  ff: FFmpeg,
  label: string,
): Promise<CheckRecord> {
  await ff.writeFile("loop_in.mp4", await fetchFile(file));
  // Same probe shape the Python harness shows the model (probe.schema.json subset).
  const inProbe = { ...(await probeViaLog(ff, "loop_in.mp4")), size_bytes: file.size };
  // Fresh output per run: ffmpeg.wasm has no stdin to confirm overwrites, and leftover frames
  // from a failed run would inflate the F7 count.
  const outFor = (n: number) =>
    task.family === "F7" ? `loop_frames_${n}/%04d.png` : `loop_out_${n}.mp4`;
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
  let firstReply = "",
    runs = 0,
    invalid = 0,
    passed = false,
    ended = "turn_budget";
  const t0 = performance.now();
  for (let turn = 0; turn < MAX_TURNS && ended === "turn_budget"; turn++) {
    const text = await chat(messages);
    if (turn === 0) firstReply = text.slice(0, 300);
    const action = parseAction(text);
    let obs: unknown;
    if ("error" in action) {
      invalid++;
      obs = { error: action.error };
    } else if (action.action === "run") {
      // Fresh output per run; the F7 frame dir must exist before ffmpeg writes into it.
      const outName = outFor(runs + 1);
      if (task.family === "F7")
        await ff.createDir(`loop_frames_${runs + 1}`).catch(() => undefined);
      const res = await runValidated(
        ff,
        action,
        { in: "loop_in.mp4", out: outName },
        { inputs: new Set(["clip"]), outputs: new Set(["out1"]) },
      );
      if (res.rejected !== null) {
        obs = { run_ok: false, rejected: res.rejected };
      } else {
        runs++;
        const r = res.exec;
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
    name: `mini_loop_${task.family}_${label}`,
    // ok = a model-written, validated command actually ran in ffmpeg.wasm (the Phase 0 exit
    // criterion); whether the output passed the check is reported separately as modelPassed.
    ok: runs > 0,
    ms: performance.now() - t0,
    detail: {
      reachedFfmpeg: runs > 0,
      modelPassed: passed,
      runs,
      invalidTurns: invalid,
      ended,
      firstReply,
    },
  };
  record(rec);
  return rec;
}
