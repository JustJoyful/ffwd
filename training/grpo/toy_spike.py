"""Phase 0 toy multi-turn GRPO run (PHASES Phase 0, D-018): measures GPU-hours per step and proves
checkpoint/resume. LoRA on Qwen3-0.6B, toy F1 trim tasks, HF generation inside our rollout_func.

  uv run --group train python -m training.grpo.toy_spike --steps 10 --ckpt-dir /kaggle/working/ckpt
  ... same command + --resume after an interruption

shortcut: generation uses transformers .generate (slow, no vLLM), so GPU-hours/step is an UPPER
bound; Phase 1 switches to vLLM [VERIFY on T4] once the loop is proven.
"""

import argparse
import json
import time
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig
from transformers import TrainerCallback
from transformers.trainer_utils import get_last_checkpoint
from trl import GRPOConfig, GRPOTrainer

from training import config
from training.corpus.make_synthetic import make_corpus
from training.grpo.rollout import Generator, make_rollout_func, prompt_messages
from training.taskgen.toy import make_toy_tasks


class StepTimer(TrainerCallback):
    """One JSON line per optimizer step: wall seconds, GPU-hours, reward stats. The Trainer calls
    on_log AFTER on_step_end, so the row is held until that step's metrics arrive."""

    def __init__(self, path: Path, n_gpus: int):
        self.path, self.n_gpus, self.t0, self.pending = path, n_gpus, None, None

    def on_step_begin(self, args, state, control, **kw):
        self.t0 = time.perf_counter()

    def on_step_end(self, args, state, control, **kw):
        seconds = round(time.perf_counter() - self.t0, 3)
        self.pending = {
            "step": state.global_step,
            "seconds": seconds,
            "gpu_hours": round(seconds * self.n_gpus / 3600, 6),
            "n_gpus": self.n_gpus,
        }

    def on_log(self, args, state, control, logs=None, **kw):
        logs = logs or {}
        if self.pending is None or "reward" not in logs:
            return
        row = self.pending | {
            "mean_reward": float(logs["reward"]),
            "reward_std": float(logs.get("reward_std", "nan")),
        }
        with self.path.open("a") as f:
            f.write(json.dumps(row) + "\n")
        self.pending = None


def hf_generator_for(temperature: float):
    def factory(trainer) -> Generator:
        model = trainer.accelerator.unwrap_model(trainer.model)
        tok = trainer.processing_class
        im_end = tok.convert_tokens_to_ids("<|im_end|>")

        def generate(ids: list[int], max_new_tokens: int) -> tuple[list[int], list[float]]:
            x = torch.tensor([ids], device=model.device)
            was_training = model.training
            model.eval()
            with torch.no_grad():
                out = model.generate(
                    x,
                    attention_mask=torch.ones_like(x),
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=temperature,
                    top_p=1.0,
                    top_k=0,
                    eos_token_id=im_end,
                    pad_token_id=tok.pad_token_id,
                    output_scores=True,
                    return_dict_in_generate=True,
                )
            if was_training:
                model.train()
            new = out.sequences[0, len(ids) :].tolist()
            # logprob of each sampled token under the sampling distribution (temperature applied)
            lps = [
                torch.log_softmax(s[0].float(), -1)[t].item()
                for s, t in zip(out.scores, new, strict=True)
            ]
            return new, lps

        return generate

    return factory


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=10)
    ap.add_argument("--ckpt-dir", type=Path, required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--model", default="Qwen/Qwen3-0.6B")
    ap.add_argument("--num-generations", type=int, default=4)  # group size
    ap.add_argument("--prompts-per-step", type=int, default=4)
    ap.add_argument("--max-new-tokens", type=int, default=256)  # per turn
    ap.add_argument("--max-runs", type=int, default=2)
    ap.add_argument("--save-steps", type=int, default=2)  # 10 steps → checkpoints 2,4,6,8,10
    ap.add_argument("--seed", type=int, default=config.BOOTSTRAP_SEED)
    ap.add_argument("--allow-cpu", action="store_true", help="debug only: train without a GPU")
    a = ap.parse_args(argv)
    if not torch.cuda.is_available() and not a.allow_cpu:
        # fail fast: an unattended run would otherwise crawl on CPU for hours while holding a GPU session
        raise SystemExit(
            "no CUDA GPU visible (check the accelerator setting / torch build); refusing to train"
        )

    manifest = config.CORPUS_DIR / "manifest.json"
    if manifest.exists():
        records = json.loads(manifest.read_text())
    else:  # e.g. a fresh Kaggle session: regenerate the synthetic corpus
        records = make_corpus(config.CORPUS_DIR)
    corpus = {r["id"]: config.CORPUS_DIR / r["file"] for r in records}

    tasks = make_toy_tasks(16, seed=a.seed)
    dataset = Dataset.from_list([{"prompt": prompt_messages(t, corpus)} for t in tasks])
    bf16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()  # T4: False → fp16
    n_gpus = max(torch.cuda.device_count(), 1)
    a.ckpt_dir.mkdir(parents=True, exist_ok=True)

    args = GRPOConfig(
        output_dir=str(a.ckpt_dir),
        max_steps=a.steps,
        seed=a.seed,
        report_to="none",
        num_generations=a.num_generations,
        per_device_train_batch_size=a.num_generations,
        gradient_accumulation_steps=a.prompts_per_step,  # one optimizer step = prompts_per_step groups
        max_completion_length=a.max_runs * 2 * a.max_new_tokens + 2048,
        beta=0.0,  # no reference model: saves memory on 16 GB T4s; fine for a throughput spike
        learning_rate=1e-5,
        temperature=1.0,
        logging_steps=1,
        save_strategy="steps",
        save_steps=a.save_steps,
        save_total_limit=2,
        bf16=bf16,
        fp16=not bf16 and torch.cuda.is_available(),
        gradient_checkpointing=True,
    )
    rollout = make_rollout_func(
        tasks,
        corpus,
        hf_generator_for(args.temperature),
        jobs_root=config.JOBS_DIR / "grpo-toy",
        max_new_tokens=a.max_new_tokens,
        max_runs=a.max_runs,
    )
    trainer = GRPOTrainer(
        model=a.model,
        args=args,
        train_dataset=dataset,
        rollout_func=rollout,
        reward_funcs=[lambda completions, toy_reward, **kw: toy_reward],
        peft_config=LoraConfig(
            r=16, lora_alpha=32, target_modules="all-linear", task_type="CAUSAL_LM"
        ),
    )
    trainer.add_callback(StepTimer(a.ckpt_dir / "toy_metrics.jsonl", n_gpus))
    resume = get_last_checkpoint(str(a.ckpt_dir)) if a.resume else None
    if a.resume and resume is None:
        raise SystemExit(f"--resume given but no checkpoint in {a.ckpt_dir}")
    trainer.train(resume_from_checkpoint=resume)


if __name__ == "__main__":
    main()
