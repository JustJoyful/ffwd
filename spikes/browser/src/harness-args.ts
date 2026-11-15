// Argument rewriting done by the HARNESS, never by the model (RULES §1.3: the model only names ids).
import { FFMPEG_THREADS } from "./config";

/**
 * Insert `-threads N` right before every output token.
 *
 * Why: in @ffmpeg/core-mt 0.12.10 (FFmpeg 5.1.4) every re-encode deadlocks when FFmpeg auto-picks
 * its thread count; stream copy is unaffected (Phase 0 finding, reports/2026-11-15-phase-0/summary.md).
 * Placing the cap last means it also overrides any `-threads` the model wrote earlier (the allowlist
 * permits the option). Native FFmpeg (Python harness, helper) has no such problem and is not capped.
 */
export function capThreads(args: string[], n: number = FFMPEG_THREADS): string[] {
  return args.flatMap((a) => (/^\{out:/.test(a) ? ["-threads", String(n), a] : [a]));
}

/** Replace {in:id}/{out:id} with in-memory FS names. Only ever called on validated args. */
export function substitute(args: string[], inName: string, outName: string): string[] {
  return args.map((a) => (/^\{in:/.test(a) ? inName : /^\{out:/.test(a) ? outName : a));
}

/** The exact argv handed to ffmpeg.wasm for a validated model action. */
export function harnessArgs(args: string[], inName: string, outName: string): string[] {
  return substitute(capThreads(args), inName, outName);
}
