import json
import os

import pytest

from training import config
from training.env import chat_template as ct

GOLDEN = json.loads((config.PROTOCOL_DIR / "conformance" / "chat-template.json").read_text())[
    "cases"
]
CONV = [
    {"role": "system", "content": "SYS"},
    {"role": "user", "content": "U1"},
    {"role": "assistant", "content": '{"action": "run"}'},
    {"role": "user", "content": '{"run_ok": true}'},
    {"role": "assistant", "content": '{"action": "finish"}'},
]


@pytest.fixture(scope="module")
def tok():
    pytest.importorskip("transformers")
    from transformers import AutoTokenizer

    try:
        t = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B", local_files_only=True)
    except OSError:
        pytest.skip("Qwen3 tokenizer not in the local HF cache")
    return ct.install(t)


@pytest.mark.parametrize("case", GOLDEN, ids=[c["name"] for c in GOLDEN])
def test_render_matches_golden(case):
    assert (
        ct.render(case["messages"], add_generation_prompt=case["add_generation_prompt"])
        == case["rendered"]
    )


@pytest.mark.parametrize("case", GOLDEN, ids=[c["name"] for c in GOLDEN])
def test_jinja_template_equals_python_render(case):
    jinja2 = pytest.importorskip("jinja2")
    got = jinja2.Template(ct.AGENT_CHAT_TEMPLATE).render(
        messages=case["messages"], add_generation_prompt=case["add_generation_prompt"]
    )
    assert got == case["rendered"]


def test_every_assistant_turn_has_the_empty_think_block():
    text = ct.render(CONV, add_generation_prompt=True)
    assert text.count("<think>\n\n</think>\n\n") == 3  # two history turns + the generation prompt


def test_hf_tokenizer_with_agent_template_equals_render(tok):
    for case in GOLDEN:
        hf = tok.apply_chat_template(
            case["messages"], add_generation_prompt=case["add_generation_prompt"], tokenize=False
        )
        assert hf == case["rendered"]


def test_stock_qwen3_template_differs_which_is_why_we_ship_our_own(tok):
    from transformers import AutoTokenizer

    stock = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B", local_files_only=True)
    text = stock.apply_chat_template(
        CONV[:4], add_generation_prompt=True, enable_thinking=False, tokenize=False
    )
    assert text != ct.render(CONV[:4], add_generation_prompt=True)
    assert text.count("<think>") == 1  # stock keeps the block only on the newest turn


def test_stream_equals_tokenized_rendering(tok):
    ids, _ = ct.tokenize_with_mask(CONV, tok)
    full = ct.render(CONV, add_generation_prompt=False).removesuffix(
        "\n"
    )  # the stream ends at the final <|im_end|>
    assert ids == tok.encode(full, add_special_tokens=False)


def test_mask_covers_only_assistant_replies_and_their_im_end(tok):
    ids, mask = ct.tokenize_with_mask(CONV, tok)
    assert len(ids) == len(mask)
    trained = tok.decode([i for i, m in zip(ids, mask, strict=True) if m])
    assert trained == '{"action": "run"}<|im_end|>{"action": "finish"}<|im_end|>'


def test_trailing_unanswered_observation_is_dropped(tok):
    ids, mask = ct.tokenize_with_mask([*CONV, {"role": "user", "content": "{}"}], tok)
    assert tok.decode(ids).endswith('{"action": "finish"}<|im_end|>') and mask[-1] == 1


@pytest.mark.skipif(
    not os.environ.get("LLAMA_SERVER_URL"),
    reason="needs llama-server started with --chat-template-file",
)
def test_llama_server_renders_the_same_bytes():
    import httpx2 as httpx  # noqa: PLC0415  (openai's transport; present in the env)

    url = os.environ["LLAMA_SERVER_URL"].rstrip("/")
    for case in GOLDEN:
        r = httpx.post(f"{url}/apply-template", json={"messages": case["messages"]}, timeout=30)
        assert r.json()["prompt"] == case["rendered"] or case["add_generation_prompt"] is False
