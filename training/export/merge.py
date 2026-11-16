"""Merge a LoRA adapter into its base model and save a standalone HF model that carries the AGENT chat template (D-026).

uv run --group train python -m training.export.merge --base Qwen/Qwen3-0.6B --adapter <dir> --out <dir>

Merging happens in fp16 (the dtype the GRPO stage and the GGUF/MLC converters expect). The tokenizer is saved with
the agent template so every downstream runtime (llama.cpp GGUF metadata, MLC conv_template source) inherits it.
"""

import argparse
from pathlib import Path


def merge_lora(base: str, adapter: Path, out: Path, dtype: str = "float16") -> Path:
    import torch  # noqa: PLC0415
    from peft import PeftModel  # noqa: PLC0415
    from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: PLC0415

    from training.env.chat_template import install  # noqa: PLC0415

    model = AutoModelForCausalLM.from_pretrained(base, dtype=getattr(torch, dtype))
    merged = PeftModel.from_pretrained(model, str(adapter)).merge_and_unload()
    out.mkdir(parents=True, exist_ok=False)  # never overwrite an earlier export
    merged.save_pretrained(out, safe_serialization=True)
    install(AutoTokenizer.from_pretrained(base)).save_pretrained(out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen3-0.6B")
    ap.add_argument("--adapter", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    print(merge_lora(a.base, a.adapter, a.out))


if __name__ == "__main__":
    main()
