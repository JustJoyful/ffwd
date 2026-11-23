"""The token-id conformance file (eval/gen_chat_template_tokens.py): Python render == stored text; ids == HF tokenizer."""

import json

import pytest

from training import config
from training.env import chat_template as ct

CASES = json.loads((config.PROTOCOL_DIR / "conformance" / "chat-template-tokens.json").read_text())[
    "cases"
]
IDS = [c["name"] for c in CASES]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_render_matches_stored_text(case):
    assert (
        ct.render(case["messages"], add_generation_prompt=case["add_generation_prompt"])
        == case["rendered"]
    )


def test_every_case_has_token_ids():
    for c in CASES:
        assert c["token_ids"] and all(isinstance(i, int) and i >= 0 for i in c["token_ids"])


def test_hf_tokenizer_ids_equal_the_llama_cpp_ids():
    pytest.importorskip("transformers")
    from transformers import AutoTokenizer

    try:
        tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B", local_files_only=True)
    except OSError:
        pytest.skip("Qwen3 tokenizer not in the local HF cache")
    for c in CASES:
        assert tok(c["rendered"], add_special_tokens=False).input_ids == c["token_ids"], c["name"]
