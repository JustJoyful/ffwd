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
from trl import GRPOConfig, GRPOTrainer

from training import config
from training.corpus.make_synthetic import ensure_corpus
from training.env.chat_template import install as install_agent_template
from training.grpo.ckpt_sync import (
    SyncCallback,
    local_latest,
    remote_from_args,
    restore_latest,
    restore_metrics,
)
from training.grpo.rollout import Generator, make_rollout_func, prompt_messages
from training.grpo.taskfilter import apply_filter
from training.grpo.telemetry import TelemetryLog, grpo_reward
from training.taskgen.toy import CLIPS as TOY_CLIPS
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
    ap.add_argument("--precision", choices=["auto", "bf16", "fp16"], default="auto")
    ap.add_argument(
        "--hub-repo",
        help="private HF Hub repo id for off-box checkpoints (needs HF_TOKEN write token)",
    )
    ap.add_argument("--sync-dir", type=Path, help="directory acting as the remote (local tests)")
    ap.add_argument(
        "--keep-last",
        type=int,
        default=None,
        help="keep only the newest N remote checkpoints (dir remote)",
    )
    ap.add_argument(
        "--reward",
        choices=["toy", "v1"],
        default="toy",
        help="toy = Phase 0 reward; v1 = ARCHITECTURE §7.4 draft terms",
    )
    ap.add_argument(
        "--shuffle-rewards",
        type=int,
        default=None,
        metavar="SEED",
        help="sanity control: permute rewards within each group (must NOT improve dev)",
    )
    ap.add_argument(
        "--task-filter",
        type=Path,
        default=None,
        help="pass_rates.json from training.grpo.taskfilter: train only on in-band tasks",
    )
    ap.add_argument(
        "--crash-after",
        type=int,
        default=None,
        metavar="STEP",
        help="test hook: hard-exit (code 42) right after checkpoint STEP is pushed off-box",
    )
    ap.add_argument("--allow-cpu", action="store_true", help="debug only: train without a GPU")
    a = ap.parse_args(argv)
    if not torch.cuda.is_available() and not a.allow_cpu:
        # fail fast: an unattended run would otherwise crawl on CPU for hours while holding a GPU session
        raise SystemExit(
            "no CUDA GPU visible (check the accelerator setting / torch build); refusing to train"
        )

    # Only the clips toy tasks use: regenerated on a fresh clone (Kaggle ships FFmpeg 6.1, so we avoid
    # recipes only verified on FFmpeg 9).
    corpus = ensure_corpus(config.CORPUS_DIR, ids={clip for clip, _ in TOY_CLIPS})

    tasks = make_toy_tasks(16, seed=a.seed)
    if a.task_filter:
        tasks = apply_filter(tasks, a.task_filter, a.ckpt_dir)  # fails loudly if nothing is in band
    dataset = Dataset.from_list([{"prompt": prompt_messages(t, corpus)} for t in tasks])
    plan = precision_plan(a.precision, native_bf16())
    print(f"precision plan: {plan}", flush=True)  # visible in Kaggle output
    if not plan["mixed_out_gemm"]:
        import trl.kernels.chunked_logprob as chunked

        chunked._MM_OUT_DTYPE = False  # see precision_plan
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
        bf16=plan["bf16"],
        fp16=plan["fp16"],
        gradient_checkpointing=True,
        model_init_kwargs={"dtype": plan["model_dtype"]},
    )
    telemetry = TelemetryLog(a.ckpt_dir / "telemetry.jsonl", a.ckpt_dir / "spotcheck")
    rollout = make_rollout_func(
        tasks,
        corpus,
        hf_generator_for(args.temperature),
        jobs_root=config.JOBS_DIR / "grpo-toy",
        max_new_tokens=a.max_new_tokens,
        max_runs=a.max_runs,
        reward_fn=grpo_reward if a.reward == "v1" else None,
        on_rollout=lambda step, records, episodes: telemetry.add(step, records, episodes),
        shuffle_seed=a.shuffle_rewards,
    )
    trainer = GRPOTrainer(
        model=a.model,
        args=args,
        train_dataset=dataset,
        rollout_func=rollout,
        reward_funcs=[lambda completions, reward, **kw: reward],
        peft_config=LoraConfig(
            r=16, lora_alpha=32, target_modules="all-linear", task_type="CAUSAL_LM"
        ),
    )
    # TokenPolicy no longer passes enable_thinking: the tokenizer must carry the agent template (D-026), which
    # keeps the empty think block exactly as enable_thinking=False did for the newest turn.
    install_agent_template(trainer.processing_class)
    metrics_path = a.ckpt_dir / "toy_metrics.jsonl"
    trainer.add_callback(StepTimer(metrics_path, n_gpus))
    remote = remote_from_args(a.hub_repo, a.sync_dir, a.keep_last)
    if remote is not None:
        extras = [metrics_path, a.ckpt_dir / "telemetry.jsonl", a.ckpt_dir / "pass_rates.json"]
        trainer.add_callback(
            SyncCallback(remote, extras, a.crash_after)
        )  # push every save off this machine
    resume = None
    if a.resume:
        # Newest of (local, remote): a fresh Kaggle session has no local checkpoint at all.
        found = (
            restore_latest(remote, a.ckpt_dir) if remote is not None else local_latest(a.ckpt_dir)
        )
        if found is None:
            raise SystemExit(f"--resume given but no checkpoint in {a.ckpt_dir} or the remote")
        for name in ("toy_metrics.jsonl", "telemetry.jsonl", "pass_rates.json"):
            restore_metrics(found, a.ckpt_dir, name)
        resume = str(found)
        print(f"resuming from {resume}", flush=True)
    trainer.train(resume_from_checkpoint=resume)


if __name__ == "__main__":
    main()
