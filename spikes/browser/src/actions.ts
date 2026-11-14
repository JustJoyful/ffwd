// Port of training/env/actions.py for the spike: same stripping rules, structural checks only
// (the full action.schema.json validation lives in the Python harness; Phase 2 adds it here).
export type Action =
  | { action: "spec"; spec: unknown }
  | { action: "ask_user"; question: string }
  | { action: "unsupported"; reason: string }
  | { action: "run"; args: string[]; inputs: string[]; outputs: string[] }
  | { action: "finish"; outputs: string[]; note?: string };

const isStrList = (x: unknown): x is string[] =>
  Array.isArray(x) && x.every((s) => typeof s === "string");

export function parseAction(text: string): Action | { error: string } {
  let body = text.replace(/<think>[\s\S]*?<\/think>/g, "").trim();
  const fence = /^```(?:json)?\s*\n?([\s\S]*?)\n?```$/.exec(body);
  if (fence) body = (fence[1] as string).trim();
  let obj: unknown;
  try {
    obj = JSON.parse(body); // JSON.parse rejects trailing prose, like raw_decode + remainder check
  } catch {
    return { error: "reply must be exactly one JSON object" };
  }
  if (typeof obj !== "object" || obj === null || Array.isArray(obj))
    return { error: "reply must be a JSON object" };
  const a = obj as Record<string, unknown>;
  switch (a.action) {
    case "run":
      return isStrList(a.args) && isStrList(a.inputs) && isStrList(a.outputs)
        ? (a as Action)
        : { error: "run needs string lists args, inputs, outputs" };
    case "finish":
      return isStrList(a.outputs) ? (a as Action) : { error: "finish needs outputs" };
    case "spec":
    case "ask_user":
    case "unsupported":
      return a as Action;
    default:
      return { error: `unknown action: ${String(a.action)}` };
  }
}
