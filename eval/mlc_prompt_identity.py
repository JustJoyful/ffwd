"""Does the MLC conversation template build EXACTLY the prompt tokens our agent chat template builds? (dev fixtures only)

Run in the MLC venv (needs `mlc_llm` + `transformers`; no repo imports, so the main uv env is untouched):

    source data/tools/mlc-env.sh
    python -m eval.mlc_prompt_identity --fixtures <prompt-fixtures.json> --mlc-model data/mlc/m3-q4f16_1 \
        --hf-tokenizer data/mlc/_src/m3 [--llama-url http://127.0.0.1:8095] [--patch] --out <result.json>

Three renderings of the same chat `messages`, compared as TOKEN IDS (that is what the model sees):
  ref   HF `apply_chat_template` with packages/protocol/prompts/chat-template.jinja (what HFPolicy / training use)
  mlc   mlc_llm Conversation built from the model's mlc-chat-config.json `conv_template`, filled exactly like
        mlc_llm.serve.engine_base.process_chat_completion_request does (system message replaces `system_message`,
        the rest is appended, then an empty assistant turn), then tokenized with the model's own tokenizer
  llama llama-server `/apply-template` + `/tokenize` (optional; the runtime the Q8_0/Q4_K_M numbers came from)
`--patch` first rewrites the conv_template of an in-memory copy so it reproduces the agent template
(see `patched_conv_template`); without it the stock `qwen3` template is measured (the "what differs" result).
"""

import argparse
import copy
import json
import re
import urllib.request
from pathlib import Path

CHAT_TEMPLATE = Path("packages/protocol/prompts/chat-template.jinja")
EMPTY_THINK = "<think>\n\n</think>\n\n"


def patched_conv_template(conv: dict) -> dict:
    """The stock qwen3 template edited so its output equals the agent jinja template.

    Two deliberate differences from stock Qwen3 (see chat-template.jinja): every assistant turn, history included,
    carries the empty think block, and the generation prompt ends with it. In MLC terms:
      role_templates.assistant  prefixes the block to every assistant message that is IN the history,
      role_empty_sep            is what follows `<|im_start|>assistant` for the turn we are about to generate
                                (stock: "\\n"; here "\\n" + the empty think block),
      strip_reasoning_in_history=false so MLC does not remove blocks from earlier assistant turns.
    The system message is NOT set here: the harness (and WebLLM) send it as a `system` chat message, which MLC
    uses in place of `system_message`.
    """
    c = copy.deepcopy(conv)
    c["role_templates"]["assistant"] = EMPTY_THINK + "{assistant_message}"
    c["role_empty_sep"] = "\n" + EMPTY_THINK
    c["strip_reasoning_in_history"] = False
    return c


def mlc_prompt(conv_dict: dict, messages: list[dict]) -> str:
    from mlc_llm.protocol.conversation_protocol import Conversation

    conv = Conversation.from_json_dict(copy.deepcopy(conv_dict))
    conv.messages = []
    for m in messages:
        if m["role"] == "system":
            conv.system_message = m["content"]
        else:
            conv.messages.append((m["role"], m["content"]))
    conv.messages.append(("assistant", None))
    parts = conv.as_prompt()
    assert len(parts) == 1 and isinstance(
        parts[0], str
    ), parts  # consecutive strings are merged into one
    return parts[0]


def llama(url: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{url}{path}", json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def first_diff(a: list[int], b: list[int]) -> int | None:
    for i, (x, y) in enumerate(zip(a, b, strict=False)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def main() -> None:
    from mlc_llm.tokenizers import Tokenizer as MlcTokenizer
    from transformers import AutoTokenizer

    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", type=Path, required=True)
    ap.add_argument("--mlc-model", type=Path, required=True)
    ap.add_argument("--hf-tokenizer", type=Path, required=True)
    ap.add_argument("--llama-url")
    ap.add_argument("--patch", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    fixtures = json.loads(a.fixtures.read_text())
    conv = json.loads((a.mlc_model / "mlc-chat-config.json").read_text())["conv_template"]
    if a.patch:
        conv = patched_conv_template(conv)
    hf = AutoTokenizer.from_pretrained(a.hf_tokenizer)
    mlc_tok = MlcTokenizer(str(a.mlc_model))  # the tokenizer the MLC engine tokenizes prompts with
    template = CHAT_TEMPLATE.read_text()
    rows = []
    for fx in fixtures:
        msgs = fx["messages"]
        ref_text = hf.apply_chat_template(
            msgs, chat_template=template, add_generation_prompt=True, tokenize=False
        )
        ref = hf(ref_text, add_special_tokens=False).input_ids
        mtext = mlc_prompt(conv, msgs)
        mlc = list(mlc_tok.encode(mtext))
        # WebLLM tokenizes each message piece on its own and concatenates the ids; every piece starts at <|im_start|>
        piecewise = [
            t
            for piece in re.split(r"(?=<\|im_start\|>)", mtext)
            if piece
            for t in mlc_tok.encode(piece)
        ]
        row = {"name": fx["name"], "n_messages": len(msgs), "ref_tokens": len(ref), "mlc_tokens": len(mlc),
               "text_identical": mtext == ref_text, "mlc_ids_identical_to_ref": mlc == ref,
               "piecewise_ids_identical_to_ref": piecewise == ref}  # fmt: skip
        if mtext != ref_text:
            i = next(
                (i for i, (x, y) in enumerate(zip(mtext, ref_text, strict=False)) if x != y),
                min(len(mtext), len(ref_text)),
            )
            row["first_text_diff"] = {"at_char": i, "mlc": mtext[max(0, i - 40) : i + 80], "ref": ref_text[max(0, i - 40) : i + 80]}  # fmt: skip
        if mlc != ref:
            row["first_token_diff_at"] = first_diff(mlc, ref)
        if a.llama_url:
            lt = llama(a.llama_url, "/apply-template", {"messages": msgs})["prompt"]
            li = llama(
                a.llama_url,
                "/tokenize",
                {"content": lt, "add_special": False, "parse_special": True},
            )["tokens"]
            row |= {"llama_text_identical_to_ref": lt == ref_text, "llama_ids_identical_to_ref": li == ref}  # fmt: skip
        rows.append(row)
    n = len(rows)
    out = {
        "patched": a.patch,
        "conv_template_used": conv,
        "n": n,
        "mlc_text_identical": sum(r["text_identical"] for r in rows),
        "mlc_ids_identical": sum(r["mlc_ids_identical_to_ref"] for r in rows),
        "piecewise_ids_identical": sum(r["piecewise_ids_identical_to_ref"] for r in rows),
        **({"llama_ids_identical": sum(r["llama_ids_identical_to_ref"] for r in rows)} if a.llama_url else {}),
        "rows": rows,
    }  # fmt: skip
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2) + "\n")
    print({k: v for k, v in out.items() if k not in ("rows", "conv_template_used")})


if __name__ == "__main__":
    main()
