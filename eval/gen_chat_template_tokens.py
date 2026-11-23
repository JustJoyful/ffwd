"""Write packages/protocol/conformance/chat-template-tokens.json: rendered prompts AND their token ids from llama.cpp.

    llama-server -m <any M3 GGUF> --port 8097 &      # the vocabulary is identical in every quant of one model
    uv run python -m eval.gen_chat_template_tokens --llama-url http://127.0.0.1:8097 \
        --fixtures reports/2026-11-23-mlc-parity/prompt-fixtures.json --gguf <that GGUF>

Cases: the three golden renders of chat-template.json plus real agent prompts (first turns of 10 dev tasks and one
multi-turn transcript, from `eval.mlc_parity fixtures`). `rendered` comes from `training.env.chat_template.render`;
`token_ids` come from the native llama.cpp `/tokenize` (parse_special true, no BOS: the same options as wllama's
`tokenize()` defaults). A JavaScript runtime must reproduce `rendered` byte for byte from `messages` and its own
tokenizer must give `token_ids` for it (ffwd-web: tests/unit/chat-template.test.js and tests/browser-gguf).
The Python side of the check (render == rendered, always) is tests/env/test_chat_template_tokens.py.
"""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from training import config
from training.env.chat_template import render

OUT = config.PROTOCOL_DIR / "conformance" / "chat-template-tokens.json"
GOLDEN = config.PROTOCOL_DIR / "conformance" / "chat-template.json"


def post(url: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(
        url + path, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    return json.load(urllib.request.urlopen(req, timeout=60))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llama-url", required=True)
    ap.add_argument("--fixtures", type=Path, required=True)
    ap.add_argument(
        "--gguf", type=Path, help="recorded in the file (name and sha256 of the GGUF served)"
    )
    a = ap.parse_args()
    cases = [
        {"name": c["name"], "messages": c["messages"], "add_generation_prompt": c["add_generation_prompt"]}
        for c in json.loads(GOLDEN.read_text())["cases"]
    ]  # fmt: skip
    cases += [
        {"name": f["name"], "messages": f["messages"], "add_generation_prompt": True}
        for f in json.loads(a.fixtures.read_text())
    ]
    for c in cases:
        c["rendered"] = render(c["messages"], add_generation_prompt=c["add_generation_prompt"])
        c["token_ids"] = post(
            a.llama_url, "/tokenize", {"content": c["rendered"], "add_special": False, "parse_special": True}
        )["tokens"]  # fmt: skip
    meta = {"tokenizer": "llama.cpp b12032 /tokenize (add_special false, parse_special true)"}
    if a.gguf:
        meta["gguf"] = {
            "name": a.gguf.name,
            "sha256": hashlib.sha256(a.gguf.read_bytes()).hexdigest(),
        }
    doc = (
        "Rendered prompts and llama.cpp token ids for the agent chat template (D-026). A runtime must "
        "render `rendered` byte for byte from `messages` and tokenize it to `token_ids` (parse special tokens, no BOS)."
    )
    OUT.write_text(json.dumps({"doc": doc, **meta, "cases": cases}, indent=1) + "\n")
    print(f"{len(cases)} cases, {sum(len(c['token_ids']) for c in cases)} tokens -> {OUT}")


if __name__ == "__main__":
    main()
