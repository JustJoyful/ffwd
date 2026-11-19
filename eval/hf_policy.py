"""A greedy HF-transformers chat policy for the parity check (plan T22): the merged fp16 model the GGUF was made from.

Same prompt bytes as llama-server (`--chat-template-file chat-template.jinja`, D-026): the agent template is applied
here with `chat_template=`. Same decoding as eval/configs/m1-0.6b-q8.toml: greedy, 512 new tokens, stop at <|im_end|>.
"""

from pathlib import Path

from training import config


class HFPolicy:
    def __init__(self, model_dir: Path, max_new_tokens: int = 512, device: str | None = None):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.model_name = str(model_dir)
        self.max_new_tokens = max_new_tokens
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.template = (config.PROTOCOL_DIR / "prompts" / "chat-template.jinja").read_text()
        self.model = (
            AutoModelForCausalLM.from_pretrained(model_dir, torch_dtype=torch.float16)
            .to(self.device)
            .eval()
        )
        self.im_end = self.tok.convert_tokens_to_ids("<|im_end|>")

    def __call__(self, messages: list[dict]) -> str:
        import torch

        text = self.tok.apply_chat_template(
            messages, chat_template=self.template, add_generation_prompt=True, tokenize=False
        )
        ids = self.tok(text, return_tensors="pt", add_special_tokens=False).input_ids.to(
            self.device
        )
        with torch.no_grad():
            out = self.model.generate(
                ids,
                attention_mask=torch.ones_like(ids),
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                eos_token_id=self.im_end,
                pad_token_id=self.tok.pad_token_id,
            )
        return self.tok.decode(out[0, ids.shape[1] :], skip_special_tokens=True)
