// TypeScript port of training/env/validator.py. Kept in sync ONLY by
// packages/protocol/conformance/validator.jsonl (RULES §4.8): change both or neither.
import allowlist from "../../../packages/protocol/allowlist.json";

export type ValidationResult = { ok: boolean; reason: string | null };

class Reject extends Error {}

const IN = /^\{in:([a-z][a-z0-9_]{0,15})\}$/;
const OUT = /^\{out:([a-z][a-z0-9_]{0,15})\}$/;
const OPT = /^(-[a-z_]+)((?::[a-z0-9]+)*)$/;
const KIND_RE: Record<string, RegExp> = {
  time: /^(?:-?\d+(\.\d+)?|-?\d{1,2}:\d{2}(:\d{2})?(\.\d+)?)$/,
  number: /^-?\d+(\.\d+)?(\/\d+)?$/,
  int: /^-?\d+$/,
  bitrate: /^\d+(\.\d+)?[kKmM]?$/,
  map: /^-?\[?[A-Za-z0-9_:]+\]?\??$/,
  metadata: /^[a-z_]+=[A-Za-z0-9 _.:-]{0,64}$/,
};
const LABEL = /^[A-Za-z0-9_:]+$/;
const FILTER_NAME = /^[a-z0-9_]+$/;
const PROTOCOL_OR_PATH = /[A-Za-z][A-Za-z0-9+.-]*:\/|\.\./;
const options = allowlist.options as Record<string, string>;

function splitGraph(graph: string): string[] {
  const parts: string[] = [];
  let buf = "";
  let quoted = false;
  let bracket = false;
  for (let i = 0; i < graph.length; i++) {
    const ch = graph[i] as string;
    if (ch === "\\" && i + 1 < graph.length) {
      buf += graph.slice(i, i + 2);
      i++;
      continue;
    }
    if (ch === "'") quoted = !quoted;
    else if (!quoted && ch === "[") bracket = true;
    else if (!quoted && ch === "]") bracket = false;
    else if (!quoted && !bracket && (ch === "," || ch === ";")) {
      parts.push(buf);
      buf = "";
      continue;
    }
    buf += ch;
  }
  if (quoted || bracket) throw new Reject("unbalanced quote or bracket in filtergraph");
  parts.push(buf);
  return parts;
}

function checkFiltergraph(graph: string): void {
  for (const part of splitGraph(graph)) {
    const m = /^((?:\[[^\]]*\])*)([^[\]]*)((?:\[[^\]]*\])*)$/.exec(part.trim());
    if (!m) throw new Reject(`bad filter syntax: '${part}'`);
    for (const lm of `${m[1]}${m[3]}`.matchAll(/\[([^\]]*)\]/g)) {
      if (!LABEL.test(lm[1] as string)) throw new Reject(`bad filter label: '${lm[1]}'`);
    }
    const body = m[2] as string;
    const eq = body.indexOf("=");
    const name = eq < 0 ? body : body.slice(0, eq);
    const fargs = eq < 0 ? "" : body.slice(eq + 1);
    if (!FILTER_NAME.test(name)) throw new Reject(`bad filter syntax: '${part}'`);
    if (!allowlist.filters.includes(name)) throw new Reject(`filter not allowed: ${name}`);
    if (PROTOCOL_OR_PATH.test(fargs)) throw new Reject(`bad filter arguments for ${name}`);
  }
}

function checkValue(opt: string, kind: string, value: string): void {
  if (kind === "codec") {
    if (value !== "copy" && !allowlist.encoders.includes(value))
      throw new Reject(`codec not allowed: ${value}`);
  } else if (kind === "filtergraph") checkFiltergraph(value);
  else if (kind === "pix_fmt") {
    if (!allowlist.pix_fmts.includes(value)) throw new Reject(`bad value for ${opt}: '${value}'`);
  } else if (kind === "muxer") {
    if (!allowlist.muxers.includes(value)) throw new Reject(`muxer not allowed: ${value}`);
  } else if (kind.startsWith("enum:")) {
    if (!kind.slice(5).split(",").includes(value))
      throw new Reject(`bad value for ${opt}: '${value}'`);
  } else if (!(KIND_RE[kind] as RegExp).test(value))
    throw new Reject(`bad value for ${opt}: '${value}'`);
}

function walk(args: string[]): [string[], string[]] {
  const usedIn: string[] = [];
  const usedOut: string[] = [];
  for (let i = 0; i < args.length;) {
    const tok = args[i] as string;
    let m: RegExpExecArray | null;
    if (tok === "-i") {
      m = IN.exec(args[i + 1] ?? "");
      if (!m) throw new Reject("input must be {in:<id>}");
      usedIn.push(m[1] as string);
      i += 2;
    } else if (tok.startsWith("-")) {
      m = OPT.exec(tok);
      const kind = m ? options[m[1] as string] : undefined;
      if (!kind) throw new Reject(`option not allowed: ${tok}`);
      if (kind === "flag") {
        i += 1;
        continue;
      }
      if (i + 1 >= args.length) throw new Reject(`missing value for ${tok}`);
      checkValue(tok, kind, args[i + 1] as string);
      i += 2;
    } else if ((m = OUT.exec(tok))) {
      usedOut.push(m[1] as string);
      i += 1;
    } else throw new Reject(`unexpected positional argument: '${tok}'`);
  }
  return [usedIn, usedOut];
}

function checkIds(used: string[], declared: string[], known: Set<string>, unique: boolean): void {
  for (const x of used)
    if (!known.has(x) || !declared.includes(x)) throw new Reject(`unknown id: ${x}`);
  if (unique) {
    const dup = [...new Set(used.filter((x, i) => used.indexOf(x) !== i))].sort()[0];
    if (dup) throw new Reject(`used more than once: ${dup}`);
  }
  for (const x of declared) if (!used.includes(x)) throw new Reject(`declared but not used: ${x}`);
}

export function validateRun(
  args: string[],
  inputs: string[],
  outputs: string[],
  known: { inputs: Set<string>; outputs: Set<string> },
): ValidationResult {
  try {
    const [usedIn, usedOut] = walk(args);
    checkIds(usedIn, inputs, known.inputs, false); // inputs may repeat (A/V offset idiom)
    checkIds(usedOut, outputs, known.outputs, true);
    return { ok: true, reason: null };
  } catch (e) {
    if (e instanceof Reject) return { ok: false, reason: e.message };
    throw e;
  }
}

export function usesStreamCopyOnly(args: string[]): boolean {
  const codecs: string[] = [];
  let filtered = false;
  args.forEach((opt, i) => {
    const base = opt.split(":")[0] as string;
    if (["-c", "-codec", "-vcodec", "-acodec"].includes(base)) codecs.push(args[i + 1] ?? "");
    else if (["-vf", "-af", "-filter", "-filter_complex"].includes(base)) filtered = true;
  });
  return codecs.length > 0 && codecs.every((c) => c === "copy") && !filtered;
}
