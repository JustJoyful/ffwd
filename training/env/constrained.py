"""Prompt loading and the decoding constraint used by the "fair" small-model baselines (T4).

The constraint is the protocol's action schema WITHOUT `spec` (not needed to run or to be graded; the
small base models copied its example). It is a strict subset of packages/protocol action.schema.json;
tests check that every constrained action also validates against the real schema.
"""

from training import config


def load_prompt(name: str) -> str:
    return (config.PROTOCOL_DIR / "prompts" / name).read_text()


def _ids(min_items: int = 0) -> dict:
    return {"type": "array", "minItems": min_items, "items": {"type": "string", "maxLength": 32}}


def action_json_schema() -> dict:
    """JSON Schema for one model reply: run | finish | ask_user | unsupported."""

    def variant(name: str, fields: dict, required: list[str]) -> dict:
        return {
            "type": "object",
            "properties": {"action": {"const": name}, **fields},
            "required": ["action", *required],
            "additionalProperties": False,
        }

    text = {"type": "string", "minLength": 1, "maxLength": 300}
    return {
        "oneOf": [
            variant(
                "run",
                {
                    "args": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 64,
                        "items": {"type": "string", "maxLength": 512},
                    },
                    "inputs": _ids(),
                    "outputs": _ids(1),
                },
                ["args", "inputs", "outputs"],
            ),
            variant(
                "finish",
                {"outputs": _ids(), "note": {"type": "string", "maxLength": 300}},
                ["outputs"],
            ),
            variant("ask_user", {"question": text}, ["question"]),
            variant("unsupported", {"reason": text}, ["reason"]),
        ]
    }


def response_format() -> dict:
    """OpenAI-style structured-output request understood by llama-server."""
    return {
        "type": "json_schema",
        "json_schema": {"name": "action", "strict": True, "schema": action_json_schema()},
    }
