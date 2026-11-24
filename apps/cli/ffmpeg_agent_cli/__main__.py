"""ffmpeg-agent "<request>" file.mp4 --model model.gguf --llama-server /path/to/llama-server"""

import argparse
import sys
from pathlib import Path

from apps.cli.ffmpeg_agent_cli.agent import context_guard, run_job
from apps.cli.ffmpeg_agent_cli.release import MANIFEST, ReleaseRefused, load_release, run_canary
from apps.cli.ffmpeg_agent_cli.server import TEMPLATE, LlamaServer
from training import config
from training.env.constrained import load_prompt
from training.env.ffmpeg_pin import PinMismatch, require_pinned
from training.policies import ChatPolicy


def _confirm(lines: list[str], yes: bool):
    print("\nHere is what I understood. The finished file must be:")
    for line in lines:
        print(f"  - {line}")
    if yes:
        return True
    ans = input("Is this right? [y = yes / type a correction] ").strip()
    return True if ans.lower() in ("y", "yes", "") else ans


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ffmpeg-agent")
    ap.add_argument("request")
    ap.add_argument("file", type=Path)
    ap.add_argument(
        "--release",
        type=Path,
        help="release folder with ffwd-model.json (verified, its runtime defaults are used)",
    )
    ap.add_argument(
        "--model",
        type=Path,
        help="GGUF file; a ffwd-model.json next to it makes this a release run",
    )
    ap.add_argument(
        "--quant",
        help="release runs: use this file from the manifest instead of the shipped one, e.g. q8_0 (the "
        "evaluated Phase 1 file). It runs with llama.cpp's default KV cache and attention, as it was "
        "evaluated (RELEASE_NOTES), not the shipped file's q8_0 KV + flash attention. The canary is "
        "WebGPU-specific to the shipped file and is refused with --quant.",
    )
    ap.add_argument("--canary", action="store_true", help="release runs: check the canary first")
    ap.add_argument(
        "--llama-server", type=Path, required=True, help="path to the llama-server binary"
    )
    ap.add_argument(
        "--out", type=Path, default=None, help="output folder (default: next to the input)"
    )
    ap.add_argument("--yes", action="store_true", help="accept the model's spec without asking")
    ap.add_argument("--max-tokens", type=int, help="legacy runs only (default 512)")
    a = ap.parse_args(argv)
    root = a.release or (
        a.model.parent if a.model and (a.model.parent / MANIFEST).is_file() else None
    )
    if root is None and a.model is None:
        ap.error("give --release DIR or --model FILE")
    if a.quant and root is None:
        ap.error("--quant needs --release DIR (or --model next to a manifest)")
    if a.quant and a.canary:
        ap.error("--canary checks the shipped file only; drop --quant")
    if root is None and a.canary:
        ap.error("--canary needs a release manifest")
    if root is not None and a.max_tokens is not None:
        ap.error("--max-tokens: a release run takes max_tokens from the manifest")
    if not a.file.is_file():
        print(f"no such file: {a.file}", file=sys.stderr)
        return 4
    try:  # before any server starts; FFmpeg comes from PATH or from $FFMPEG_AGENT_PIN_HOME (see training.config)
        require_pinned()
    except (PinMismatch, OSError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 5
    # absolute: the bwrap sandbox binds the job dir by path, and a relative one makes every run fail ("Read-only file system")
    a.file = a.file.resolve()
    out_dir = (a.out or a.file.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if root is not None:
        try:
            rel = load_release(root, a.quant)
            if a.model and a.model.resolve() != rel.gguf.resolve():
                raise ReleaseRefused(
                    f"{a.model.name} is not the selected file {rel.gguf.name}; "
                    "pick another quant explicitly with --quant"
                )
        except ReleaseRefused as e:
            print(f"refused: {e}", file=sys.stderr)
            return 5
        rt = rel.runtime
        model, system = rel.gguf, rel.system_prompt
        flags = {
            "template": rel.template,
            "kv": rt["kv_cache_type"],
            "flash": rt["flash_attention"],
        }
        if (
            rel.evaluated
        ):  # RELEASE_NOTES: the evaluated Q8_0 numbers used the default (f16) KV cache, no -fa flag
            flags |= {"kv": None, "flash": None}
        n_ctx, max_tokens, temperature = rt["n_ctx"], rt["max_tokens"], rt["temperature"]
    else:
        print(
            f"warning: no {MANIFEST} next to the model; runtime defaults and files are unverified",
            file=sys.stderr,
        )
        model, system, flags = a.model, load_prompt(config.SYSTEM_PROMPT_V1), {"template": TEMPLATE}
        n_ctx, max_tokens, temperature = 4096, a.max_tokens or 512, 0.0
    with LlamaServer(a.llama_server, model, n_ctx, **flags) as server:
        if a.canary:
            ok, detail = run_canary(rel, server)
            print(f"canary {'passed' if ok else 'FAILED'}: {detail}")
            if not ok:
                return 5
        policy = context_guard(
            ChatPolicy(server.base_url, "agent", None, temperature=temperature, max_tokens=max_tokens),
            server.count_tokens, n_ctx, max_tokens,
        )  # fmt: skip
        result = run_job(
            a.request, a.file, policy, out_dir=out_dir, system_prompt=system,
            confirm=lambda lines: _confirm(lines, a.yes), ask=lambda q: input(f"{q} ").strip(),
        )  # fmt: skip
    print(("\n" if result.ok else "\n! ") + result.message)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
