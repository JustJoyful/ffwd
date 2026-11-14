"""Parse one model reply into one protocol action. The same parser is used for every system
(base Qwen3, SFT models, DeepSeek), so formatting quirks are handled identically."""

import json
import re
from dataclasses import dataclass

from training.protocol import validate

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


@dataclass(frozen=True)
class ParseError:
    message: str


def parse_action(text: str) -> dict | ParseError:
    body = _THINK.sub("", text).strip()
    if m := _FENCE.match(body):
        body = m.group(1).strip()
    try:
        obj, end = json.JSONDecoder().raw_decode(body)
    except json.JSONDecodeError as e:
        return ParseError(f"reply is not a JSON object: {e.msg}")
    if body[end:].strip():
        return ParseError("extra text after the JSON object; reply with exactly one JSON object")
    if not isinstance(obj, dict):
        return ParseError("reply must be a JSON object")
    if errors := validate("action", obj):
        return ParseError("invalid action: " + "; ".join(errors[:3]))
    return obj
