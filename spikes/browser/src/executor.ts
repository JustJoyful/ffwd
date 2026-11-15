// Browser executor: the ONLY path from a model `run` action to ffmpeg.wasm (mirrors
// training/env/executor.py). Order: allowlist validation → harness argument rewriting
// (id substitution + thread cap, see harness-args.ts) → exec. The model never sees or controls the rewriting.
import type { FFmpeg } from "@ffmpeg/ffmpeg";
import { execLogged, type Exec } from "./ffmpeg-check";
import { harnessArgs } from "./harness-args";
import { validateRun } from "./validator";

export type RunAction = { args: string[]; inputs: string[]; outputs: string[] };
export type RunOutcome = { rejected: string } | { rejected: null; exec: Exec };

export async function runValidated(
  ff: FFmpeg,
  action: RunAction,
  names: { in: string; out: string },
  known: { inputs: Set<string>; outputs: Set<string> },
): Promise<RunOutcome> {
  const v = validateRun(action.args, action.inputs, action.outputs, known);
  if (!v.ok) return { rejected: v.reason ?? "rejected" };
  return {
    rejected: null,
    exec: await execLogged(ff, harnessArgs(action.args, names.in, names.out)),
  };
}
