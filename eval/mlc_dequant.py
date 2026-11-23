"""Turn an MLC-converted model back into a plain fp16 HF model, to measure what MLC's weight format costs (dev only).

    uv run python -m eval.mlc_dequant --mlc data/mlc/m3-q4f16_1 --hf-src data/mlc/_src/m3 --out data/mlc/m3-q4f16_1-dequant

Why: the browser runs MLC weights (`q4f16_1` = int4, symmetric, groups of 32 along the input axis, fp16 scale; the
embedding / tied lm_head is quantized too). The MLC CUDA runtime could not be built on this machine (see the report), so
instead we read the CONVERTED files (`tensor-cache.json` + `params_shard_*.bin`, exactly what WebLLM downloads), undo the
packing in numpy and run the result in the same harness through HF fp16. What this keeps: every number MLC stored. What it
does not cover: the WebGPU kernels' own rounding (fp16 accumulation order), which this method cannot see.

Formats (mlc_llm/quantization/group_quantization.py, q4f16_1, no ft reorder):
  q_weight uint32 [N, K/8]: element j of a row sits in word j//8, bits 4*(j%8) .. 4*(j%8)+3 (low nibble first)
  q_scale  fp16   [N, K/32]
  value = (nibble - 7) * scale[row, j//32]          (fp16 multiply, as MLC's `dequantize` does)
MLC fuses q/k/v into `c_attn` and gate/up into `gate_up_proj` (concatenated along rows); they are split back here.
`--check` re-quantizes the original fp16 weights with the documented formula and counts how many stored words match.
"""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from safetensors.numpy import load_file, save_file

GROUP, MAXINT, PER_WORD = 32, 7, 8


def load_mlc(mlc_dir: Path) -> dict[str, np.ndarray]:
    cache = json.loads((mlc_dir / "tensor-cache.json").read_text())
    out = {}
    for shard in cache["records"]:
        blob = (mlc_dir / shard["dataPath"]).read_bytes()
        for r in shard["records"]:
            if r["dtype"] not in ("uint32", "float16"):
                raise ValueError(
                    f"{r['name']}: dtype {r['dtype']} not handled (this is a q4f16_1/q0f16 reader)"
                )
            arr = np.frombuffer(
                blob, dtype=r["dtype"], count=int(np.prod(r["shape"])), offset=r["byteOffset"]
            )
            out[r["name"]] = arr.reshape(r["shape"])
    return out


def unpack(q_weight: np.ndarray) -> np.ndarray:
    shifts = (np.arange(PER_WORD, dtype=np.uint32) * 4)[None, None, :]
    nib = (q_weight[:, :, None] >> shifts) & 0xF
    return nib.reshape(q_weight.shape[0], -1)


def dequantize(q_weight: np.ndarray, q_scale: np.ndarray) -> np.ndarray:
    nib = unpack(q_weight).astype(np.float16)
    scale = np.repeat(q_scale, GROUP, axis=1)
    return (nib - np.float16(MAXINT)) * scale  # fp16 throughout, like MLC's TE definition


def quantize(w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """MLC's `_quantize` in numpy: scale = max|w| / 7 (fp16); q = clip(round(w / scale + 7), 0, 14)."""
    w = w.astype(np.float16)
    g = w.reshape(w.shape[0], -1, GROUP)
    scale = np.abs(g).max(axis=2) / np.float16(MAXINT)
    q = np.clip(np.round(g / scale[:, :, None] + np.float16(MAXINT)), 0, 2 * MAXINT).astype(
        np.uint32
    )
    words = (q.reshape(w.shape[0], -1, PER_WORD) << (np.arange(PER_WORD, dtype=np.uint32) * 4)).sum(
        axis=2, dtype=np.uint32
    )
    return words.astype(np.uint32), scale.astype(np.float16)


def full(params: dict[str, np.ndarray], name: str) -> np.ndarray:
    """fp16 tensor `name` (a module path without .weight) from either a quantized pair or a plain weight."""
    if f"{name}.q_weight" in params:
        return dequantize(params[f"{name}.q_weight"], params[f"{name}.q_scale"])
    return params[f"{name}.weight"]


def to_hf(params: dict[str, np.ndarray], cfg: dict) -> dict[str, np.ndarray]:
    hd, nh, nkv = cfg["head_dim"], cfg["num_attention_heads"], cfg["num_key_value_heads"]
    inter = cfg["intermediate_size"]
    state = {
        "model.embed_tokens.weight": full(params, "model.embed_tokens"),
        "model.norm.weight": params["model.norm.weight"],
    }
    for i in range(cfg["num_hidden_layers"]):
        p = f"model.layers.{i}"
        qkv = full(params, f"{p}.self_attn.c_attn")
        q, k, v = np.split(qkv, [nh * hd, (nh + nkv) * hd], axis=0)
        gate, up = np.split(full(params, f"{p}.mlp.gate_up_proj"), [inter], axis=0)
        state |= {
            f"{p}.self_attn.q_proj.weight": q, f"{p}.self_attn.k_proj.weight": k, f"{p}.self_attn.v_proj.weight": v,
            f"{p}.self_attn.o_proj.weight": full(params, f"{p}.self_attn.o_proj"),
            f"{p}.self_attn.q_norm.weight": params[f"{p}.self_attn.q_norm.weight"],
            f"{p}.self_attn.k_norm.weight": params[f"{p}.self_attn.k_norm.weight"],
            f"{p}.mlp.gate_proj.weight": gate, f"{p}.mlp.up_proj.weight": up,
            f"{p}.mlp.down_proj.weight": full(params, f"{p}.mlp.down_proj"),
            f"{p}.input_layernorm.weight": params[f"{p}.input_layernorm.weight"],
            f"{p}.post_attention_layernorm.weight": params[f"{p}.post_attention_layernorm.weight"],
        }  # fmt: skip
    return {k: np.ascontiguousarray(v) for k, v in state.items()}


def compare(state: dict[str, np.ndarray], ref: dict[str, np.ndarray]) -> dict:
    """Per-tensor-class error of the MLC weights vs the original fp16 weights."""
    out = {}
    for k, v in state.items():
        r = ref[k].astype(np.float32)
        d = v.astype(np.float32) - r
        cls = k.split(".")[-2] if "layers" in k else k
        s = out.setdefault(
            cls, {"n": 0, "sq_err": 0.0, "sq_ref": 0.0, "max_abs_err": 0.0, "exact": 0}
        )
        s["n"] += d.size
        s["sq_err"] += float((d**2).sum())
        s["sq_ref"] += float((r**2).sum())
        s["max_abs_err"] = max(s["max_abs_err"], float(np.abs(d).max()))
        s["exact"] += int((d == 0).sum())
    return {c: {"rel_rmse": (s["sq_err"] / s["sq_ref"]) ** 0.5, "max_abs_err": s["max_abs_err"], "exact_share": s["exact"] / s["n"]} for c, s in out.items()}  # fmt: skip


def check_requantize(params: dict[str, np.ndarray], ref: dict[str, np.ndarray]) -> dict:
    """Does re-quantizing the ORIGINAL weights with the documented formula reproduce MLC's stored words and scales?"""
    cases = {
        "model.embed_tokens": ref["model.embed_tokens.weight"],
        "model.layers.0.mlp.down_proj": ref["model.layers.0.mlp.down_proj.weight"],
        "model.layers.0.self_attn.o_proj": ref["model.layers.0.self_attn.o_proj.weight"],
        "model.layers.5.self_attn.c_attn": np.concatenate([ref[f"model.layers.5.self_attn.{n}_proj.weight"] for n in "qkv"]),
        "model.layers.5.mlp.gate_up_proj": np.concatenate([ref[f"model.layers.5.mlp.{n}_proj.weight"] for n in ("gate", "up")]),
    }  # fmt: skip
    res = {}
    for name, w in cases.items():
        q, s = quantize(w)
        res[name] = {"words_equal": float((q == params[f"{name}.q_weight"]).mean()), "scales_equal": float((s == params[f"{name}.q_scale"]).mean())}  # fmt: skip
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mlc", type=Path, required=True)
    ap.add_argument("--hf-src", type=Path, required=True, help="the HF dir the model was converted from (config + tokenizer + reference weights)")  # fmt: skip
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--stats-out", type=Path)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    cfg = json.loads((a.hf_src / "config.json").read_text())
    params = load_mlc(a.mlc)
    state = to_hf(params, cfg)
    ref = load_file(a.hf_src / "model.safetensors")
    ref.pop("lm_head.weight", None)  # tied to the embedding
    if set(ref) != set(state):
        raise SystemExit(f"tensor names differ: {sorted(set(ref) ^ set(state))[:6]}")
    stats = {"per_class_vs_original_fp16": compare(state, ref)}
    if any(k.endswith(".q_weight") for k in params):
        stats["requantize_original_matches_mlc_files"] = check_requantize(params, ref)
    print(json.dumps(stats, indent=1))
    a.out.mkdir(parents=True)
    save_file(state, a.out / "model.safetensors", metadata={"format": "pt"})
    for f in ("config.json", "generation_config.json", "tokenizer.json", "tokenizer_config.json"):
        shutil.copy(a.hf_src / f, a.out / f)
    if a.stats_out:
        a.stats_out.parent.mkdir(parents=True, exist_ok=True)
        a.stats_out.write_text(json.dumps(stats, indent=2) + "\n")


if __name__ == "__main__":
    main()
