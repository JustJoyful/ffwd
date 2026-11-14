import { describe, expect, it } from "vitest";
import cases from "../../../packages/protocol/conformance/validator.jsonl?raw";
import { validateRun } from "../src/validator";

type Case = {
  name: string;
  args: string[];
  inputs: string[];
  outputs: string[];
  ok: boolean;
  reason_contains: string;
};
const all: Case[] = cases
  .trim()
  .split("\n")
  .map((l: string) => JSON.parse(l) as Case);

describe("matches python conformance cases", () => {
  it.each(all.map((c) => [c.name, c] as const))("%s", (_name, c) => {
    const r = validateRun(c.args, c.inputs, c.outputs, {
      inputs: new Set(c.inputs),
      outputs: new Set(c.outputs),
    });
    expect(r.ok, r.reason ?? "").toBe(c.ok);
    if (!c.ok) expect(r.reason).toContain(c.reason_contains);
  });
});
