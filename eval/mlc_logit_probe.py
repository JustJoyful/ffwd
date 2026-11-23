"""Which part of MLC q4f16_1 hurts? Teacher-forced next-token agreement on the reference model's own first replies (dev only).

    uv run --group train python -m eval.mlc_logit_probe --orig data/mlc/_src/m3 --q4 data/mlc/m3-q4f16_1-dequant \
        --ref-run reports/2026-11-22-m3-ckpt60-dev/grpo-m3-ckpt60-q8 --n 40 --out reports/<date>-mlc-parity/logit-probe.json

For the first N sample tasks the prompt is the real first-turn prompt and the continuation is the Q8_0 run's first assistant
reply. Each model variant is fed prompt + reply (teacher forcing, no sampling) and we count how often its greedy next token
equals the token the reference emitted, and its mean NLL on those tokens. Variants (all fp16 weights, CPU, fp32 compute):
  orig        the unquantized merged model (sanity: should be ~100%)
  q4          every MLC q4f16_1 tensor, embedding / tied lm_head included (what the browser would run)
  q4_body     MLC q4 transformer layers, ORIGINAL embedding / lm_head
  q4_embed    original transformer layers, MLC q4 embedding / lm_head
This does not decide success (that is the harness run); it says where the damage comes from.
"""

import argparse
import json
import tomllib
from pathlib import Path

from eval.hf_parity import sample_ids, turns
from eval.mlc_parity import CFG
from eval.quant_parity import SEED
from eval.quant_parity import N as SAMPLE_N
from eval.run_baseline import load_corpus
from training.env.constrained import load_prompt
from training.env.loop import initial_messages
from training.env.probe import probe
from training.taskgen.loader import load_tasks

EMBED = "model.embed_tokens.weight"


VARIANTS = {  # name -> (source of the transformer layers, source of the embedding / tied lm_head)
    "orig": ("orig", "orig"),
    "q4": ("q4", "q4"),
    "q4_body": ("q4", "orig"),
    "q4_embed": ("orig", "q4"),
}


def load_into(model, body, embed) -> None:
    """Copy tensors one by one from two safetensors handles (fp16 -> the model's fp32); keeps RAM at one model."""
    for name, param in model.named_parameters():
        src = embed if name == EMBED else body
        param.data.copy_(src.get_tensor(name))


def main() -> None:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    ap = argparse.ArgumentParser()
    ap.add_argument("--orig", type=Path, required=True)
    ap.add_argument("--q4", type=Path, required=True)
    ap.add_argument("--ref-run", type=Path, required=True)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    tok = AutoTokenizer.from_pretrained(a.q4)
    template = (
        CFG.parent.parent.parent / "packages/protocol/prompts/chat-template.jinja"
    ).read_text()
    all_tasks = load_tasks("dev", "dev-eval")  # dev only
    ids = sample_ids(all_tasks, SAMPLE_N, SEED)[: a.n]
    by_id = {t["id"]: t for t in all_tasks}
    corpus, system = load_corpus(), load_prompt(tomllib.loads(CFG.read_text())["system_prompt"])
    ref_turns = turns(a.ref_run)
    batch = []  # (prompt ids, reply ids incl. <|im_end|>)
    for tid in ids:
        t = by_id[tid]
        msgs = initial_messages(t, {c: probe(corpus[c]) for c in t["inputs"]}, system)
        text = tok.apply_chat_template(
            msgs, chat_template=template, add_generation_prompt=True, tokenize=False
        )
        prompt = tok(text, add_special_tokens=False).input_ids
        reply = tok(ref_turns[tid][0] + "<|im_end|>", add_special_tokens=False).input_ids
        batch.append((prompt, reply))
    model = AutoModelForCausalLM.from_pretrained(a.q4, dtype=torch.float32).eval()
    out = {"n_tasks": len(batch), "ref_run": str(a.ref_run), "variants": {}}
    from safetensors import safe_open

    files = {
        "orig": safe_open(a.orig / "model.safetensors", "pt"),
        "q4": safe_open(a.q4 / "model.safetensors", "pt"),
    }
    for name, (body, embed) in VARIANTS.items():
        load_into(model, files[body], files[embed])
        hit = tot = 0
        nll = 0.0
        diff_tasks = 0
        for prompt, reply in batch:
            ids_t = torch.tensor([prompt + reply])
            with torch.no_grad():
                logits = model(ids_t).logits[0, len(prompt) - 1 : -1].float()
            tgt = torch.tensor(reply)
            ok = logits.argmax(-1) == tgt
            hit, tot = hit + int(ok.sum()), tot + len(reply)
            nll += float(torch.nn.functional.cross_entropy(logits, tgt, reduction="sum"))
            diff_tasks += int(not ok.all())
        out["variants"][name] = {"n_tokens": tot, "top1_agree": hit / tot, "mean_nll": nll / tot, "tasks_with_any_disagreement": diff_tasks}  # fmt: skip
        print(name, out["variants"][name], flush=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
