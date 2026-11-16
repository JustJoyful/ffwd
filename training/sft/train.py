"""LoRA SFT on masked multi-turn agent streams (plan T16). Kaggle T4 (fp16) or any CUDA GPU.

  uv run --group train python -m training.sft.train --data data/sft/examples.jsonl --ckpt-dir /kaggle/working/sft \
      --hub-repo JustJoyful/ffmpeg-agent-ckpt-sft --epochs 3
  ... same command + --resume after an interruption (the newest of local/remote checkpoint)

Checkpoints go off-box after every save (D-022). Labels are pre-masked (assistant actions only), so this script
trains on exactly the examples training.sft.build wrote; it never tokenizes text itself.
"""

import argparse
import json
from pathlib import Path

import torch
from peft import LoraConfig
from transformers import AutoModelForCausalLM, Trainer, TrainingArguments

from training import config
from training.grpo.ckpt_sync import SyncCallback, local_latest, remote_from_args, restore_latest
from training.precision import native_bf16, precision_plan
from training.sft.dataset import IGNORE


class Collator:
    def __init__(self, pad_id: int):
        self.pad_id = pad_id

    def __call__(self, batch: list[dict]) -> dict:
        n = max(len(b["input_ids"]) for b in batch)
        ids = torch.full((len(batch), n), self.pad_id, dtype=torch.long)
        labels = torch.full((len(batch), n), IGNORE, dtype=torch.long)
        mask = torch.zeros((len(batch), n), dtype=torch.long)
        for i, b in enumerate(batch):  # right padding: loss only on real assistant tokens
            k = len(b["input_ids"])
            ids[i, :k], labels[i, :k], mask[i, :k] = (
                torch.tensor(b["input_ids"]),
                torch.tensor(b["labels"]),
                1,
            )
        return {"input_ids": ids, "labels": labels, "attention_mask": mask}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def main(argv: list[str] | None = None) -> None:
    h = config.SFT_HPARAMS
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-0.6B")
    ap.add_argument(
        "--data", type=Path, required=True, help="examples.jsonl from training.sft.build"
    )
    ap.add_argument("--val", type=Path, default=None)
    ap.add_argument("--ckpt-dir", type=Path, required=True)
    ap.add_argument("--epochs", type=float, default=h["epochs"])
    ap.add_argument("--lr", type=float, default=h["lr"])
    ap.add_argument("--max-steps", type=int, default=-1, help="smoke tests only")
    ap.add_argument("--save-steps", type=int, default=50)
    ap.add_argument("--seed", type=int, default=config.TASKGEN_SEED)
    ap.add_argument("--precision", choices=["auto", "bf16", "fp16"], default="auto")
    ap.add_argument("--hub-repo")
    ap.add_argument("--sync-dir", type=Path)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--allow-cpu", action="store_true", help="debug only: fp32 on CPU")
    a = ap.parse_args(argv)
    if not torch.cuda.is_available() and not a.allow_cpu:
        raise SystemExit(
            "no CUDA GPU visible; refusing to train (use --allow-cpu for a smoke test)"
        )
    cpu = not torch.cuda.is_available()
    plan = (
        {"bf16": False, "fp16": False, "model_dtype": torch.float32}
        if cpu
        else precision_plan(a.precision, native_bf16())
    )
    print(f"precision plan: {plan}", flush=True)
    train, val = load_jsonl(a.data), (load_jsonl(a.val) if a.val else None)
    model = AutoModelForCausalLM.from_pretrained(a.model, dtype=plan["model_dtype"])
    if not cpu:
        model.to("cuda")
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()  # LoRA + gradient checkpointing needs grads flowing into the embeddings
    from peft import get_peft_model

    lo = config.SFT_LORA
    model = get_peft_model(
        model,
        LoraConfig(
            r=lo["r"],
            lora_alpha=lo["alpha"],
            lora_dropout=lo["dropout"],
            target_modules="all-linear",
            task_type="CAUSAL_LM",
        ),
    )
    from transformers import AutoTokenizer

    pad = AutoTokenizer.from_pretrained(a.model).pad_token_id
    a.ckpt_dir.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(
        output_dir=str(a.ckpt_dir), num_train_epochs=a.epochs, max_steps=a.max_steps, learning_rate=a.lr,
        per_device_train_batch_size=h["per_device_batch"], gradient_accumulation_steps=h["grad_accum"],
        warmup_ratio=h["warmup_ratio"], lr_scheduler_type="cosine", logging_steps=5, save_strategy="steps",
        save_steps=a.save_steps, save_total_limit=2, eval_strategy="steps" if val else "no", eval_steps=a.save_steps,
        bf16=plan["bf16"], fp16=plan["fp16"], seed=a.seed, report_to="none", remove_unused_columns=False,
        use_cpu=cpu, gradient_checkpointing=False,
    )  # fmt: skip
    trainer = Trainer(
        model=model, args=args, train_dataset=train, eval_dataset=val, data_collator=Collator(pad)
    )
    remote = remote_from_args(a.hub_repo, a.sync_dir)
    if remote is not None:
        trainer.add_callback(SyncCallback(remote))
    resume = None
    if a.resume:
        found = (
            restore_latest(remote, a.ckpt_dir) if remote is not None else local_latest(a.ckpt_dir)
        )
        if found is None:
            raise SystemExit(f"--resume given but no checkpoint in {a.ckpt_dir} or the remote")
        resume = str(found)
        print(f"resuming from {resume}", flush=True)
    trainer.train(resume_from_checkpoint=resume)
    model.save_pretrained(a.ckpt_dir / "adapter-final")


if __name__ == "__main__":
    main()
