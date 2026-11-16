"""ffmpeg-agent "<request>" file.mp4 --model model.gguf --llama-server /path/to/llama-server"""

import argparse
import sys
from pathlib import Path

from apps.cli.ffmpeg_agent_cli.agent import run_job
from apps.cli.ffmpeg_agent_cli.server import LlamaServer
from training import config
from training.env.constrained import load_prompt
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
    ap.add_argument("--model", type=Path, required=True, help="GGUF model file")
    ap.add_argument(
        "--llama-server", type=Path, required=True, help="path to the llama-server binary"
    )
    ap.add_argument(
        "--out", type=Path, default=None, help="output folder (default: next to the input)"
    )
    ap.add_argument("--yes", action="store_true", help="accept the model's spec without asking")
    ap.add_argument("--max-tokens", type=int, default=512)
    a = ap.parse_args(argv)
    if not a.file.is_file():
        print(f"no such file: {a.file}", file=sys.stderr)
        return 4
    out_dir = a.out or a.file.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    with LlamaServer(a.llama_server, a.model) as server:
        policy = ChatPolicy(
            server.base_url, "agent", None, temperature=0.0, max_tokens=a.max_tokens
        )
        result = run_job(
            a.request, a.file, policy, out_dir=out_dir, system_prompt=load_prompt(config.SYSTEM_PROMPT_V1),
            confirm=lambda lines: _confirm(lines, a.yes), ask=lambda q: input(f"{q} ").strip(),
        )  # fmt: skip
    print(("\n" if result.ok else "\n! ") + result.message)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
