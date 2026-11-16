"""Precision choice shared by every trainer (SFT, GRPO): bf16 on Ampere+, fp16 on T4 (D-018, T5 fix)."""

import torch


def native_bf16() -> bool:
    """bf16 in hardware (compute capability >= 8.0). Not torch.cuda.is_bf16_supported(): that counts
    emulation and returns True on a T4, which sent the Kaggle run down the crashing bf16 path."""
    return torch.cuda.is_available() and torch.cuda.get_device_capability() >= (8, 0)


def precision_plan(precision: str, bf16_supported: bool) -> dict:
    """bf16 on Ampere+; fp16 on T4 (no bf16 hardware). On the fp16 path TRL's chunked-logprob kernel
    must not use torch.addmm(out_dtype=float32): that mixed-precision GEMM needs compute capability
    >= 8.0 (crashed on Kaggle T4). Its fallback upcasts to fp32 first: same math, a bit slower."""
    use_bf16 = precision == "bf16" or (precision == "auto" and bf16_supported)
    return {
        "bf16": use_bf16,
        "fp16": not use_bf16,
        "model_dtype": torch.bfloat16 if use_bf16 else torch.float16,
        "mixed_out_gemm": use_bf16,
    }
