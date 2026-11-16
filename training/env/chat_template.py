"""The agent chat template (D-026) and token streams with assistant-only masks.

`AGENT_CHAT_TEMPLATE` is installed on the tokenizer for training and shipped with every export, so the
rendering used while training is the rendering used at inference. `render` is a dependency-free
implementation of the same template (goldens, the TypeScript port in Phase 2); tests prove it equals the Jinja
template, the HF tokenizer, the rollout's TokenPolicy stream and, when a server is up, llama.cpp.
"""

from training import config
from training.grpo.rollout import TokenPolicy

AGENT_CHAT_TEMPLATE = (config.PROTOCOL_DIR / "prompts" / "chat-template.jinja").read_text()
EMPTY_THINK = "<think>\n\n</think>\n\n"


def render(messages: list[dict], *, add_generation_prompt: bool) -> str:
    out = []
    for m in messages:
        think = EMPTY_THINK if m["role"] == "assistant" else ""
        out.append(f"<|im_start|>{m['role']}\n{think}{m['content']}<|im_end|>\n")
    if add_generation_prompt:
        out.append(f"<|im_start|>assistant\n{EMPTY_THINK}")
    return "".join(out)


def install(tokenizer):
    """Set the agent template on a HF tokenizer (returns it)."""
    tokenizer.chat_template = AGENT_CHAT_TEMPLATE
    return tokenizer


def tokenize_with_mask(messages: list[dict], tokenizer) -> tuple[list[int], list[int]]:
    """(input_ids, assistant_mask) for [system, user, assistant, user, assistant, ...].

    Built by replaying the conversation through the SAME TokenPolicy the rollouts use, so the SFT stream is
    byte-for-byte the stream GRPO generates. mask=1 only on assistant replies and their <|im_end|>.
    A trailing user message (an observation nobody answered) is dropped; the stream ends at an assistant turn.
    """
    im_end = tokenizer.convert_tokens_to_ids("<|im_end|>")
    replies = iter(m["content"] for m in messages[2:] if m["role"] == "assistant")

    def scripted(_ids, _n):
        ids = tokenizer.encode(next(replies), add_special_tokens=False) + [im_end]
        return ids, [0.0] * len(ids)

    policy = TokenPolicy(tokenizer, scripted, max_new_tokens=10**6)
    history = list(messages[:2])
    i = 2
    while i < len(messages) and messages[i]["role"] == "assistant":
        policy(history)
        history += messages[i : i + 2]
        i += 2
    ids = policy.prompt_ids + policy.completion_ids
    return ids, [0] * len(policy.prompt_ids) + policy.env_mask
