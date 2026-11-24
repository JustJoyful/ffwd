"""Shared fakes for the release tests: tiny files, never the real GGUFs."""

import hashlib
import json
from pathlib import Path

import pytest

from training import config
from training.env.chat_template import render
from training.export import release
from training.export.release import Inputs, Model

PROMPTS = config.PROTOCOL_DIR / "prompts"
USER = '{"request": "Cut the first 2 seconds off", "inputs": [], "outputs": ["out1"]}'


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


CARD = f"""---
# DRAFT front matter
# second comment
# third comment
license: apache-2.0
---

> DRAFT: for a PRIVATE repo.

# ffwd M3 (ffmpeg-agent-m3-0.6b): a test card

Repo id: `JustJoyful/ffwd-0.6b` (owner decision).

Files: `ffmpeg-agent-m3-0.6b-q8_0.gguf` sha256 `{sha(b"q8")}` and `{sha(b"q5")}`.
`llama-server -m ffmpeg-agent-m3-0.6b-q8_0.gguf`
`ffmpeg-agent-m3-0.6b-q8_0.gguf` again, and `ffmpeg-agent-m3-0.6b-q8_0.gguf`.

The user message is a JSON object with `request` and more.

## Files

the Q5_K_M file named above (shipping format), `chat-template.jinja`, `system-v1.txt`, `SHA256SUMS`, `LICENSE`. The LoRA adapter of checkpoint-60 (now on the private repo) will be included.
"""


@pytest.fixture
def inputs(tmp_path: Path) -> Inputs:
    src = tmp_path / "src"
    (src / "adapter").mkdir(parents=True)
    (src / "q5.gguf").write_bytes(b"q5")
    (src / "q8.gguf").write_bytes(b"q8")
    (src / "adapter" / "adapter_model.safetensors").write_bytes(b"lora")
    (src / "adapter" / "adapter_config.json").write_text("{}")
    (src / "card.md").write_text(CARD)
    (src / "lic.txt").write_text("licence text")
    system = (PROMPTS / "system-v1.txt").read_text()
    prompt = render(
        [{"role": "system", "content": system}, {"role": "user", "content": USER}],
        add_generation_prompt=True,
    )
    ref = {
        "model": {"sha256": sha(b"q5")},
        "ggufSha256Checked": True,
        "llamaCpp": {"build": "b1-x"},
        "prompt": prompt,
        "promptTokenCount": 7,
        "maxTokens": 3,
        "tokens": [1, 2, 3],
        "text": "abc",
        "roundTrips": True,
    }
    (src / "canary.json").write_text(json.dumps(ref))
    (src / "config.js").write_text(
        f'bytes: 2,\nsha256: "{sha(b"q5")}",\nnCtx: 8192,\nkvCache: "q8_0",\nmaxTokens: 512,\ncanaryMinMatch: 18,\n'
    )
    return Inputs(
        q5=Model(src / "q5.gguf", sha(b"q5"), 2, "Q5_K_M", "shipped"),
        q8=Model(src / "q8.gguf", sha(b"q8"), 2, "Q8_0", "evaluated"),
        adapter=src / "adapter",
        adapter_sha256=sha(b"lora"),
        card=src / "card.md",
        licence=src / "lic.txt",
        system_prompt=PROMPTS / "system-v1.txt",
        chat_template=PROMPTS / "chat-template.jinja",
        canary_reference=src / "canary.json",
        site_config=src / "config.js",
        pins=(release.SYSTEM_PROMPT_SHA, release.CHAT_TEMPLATE_SHA, sha(b"licence text")),
    )
