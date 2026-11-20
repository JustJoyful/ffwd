"""The Phase 1 multi-turn GRPO run (plan T19/T20). Generalises toy_spike: init from the merged SFT model, reward v1,
M1-pass-rate task filter, lockstep batched rollouts, preregistered stop rules, GPU-hour cap, off-box checkpoints.

  uv run --group train python -m training.grpo.main_run --init <merged SFT dir or HF id> --pass-rates pass_rates.json \
      --hub-repo JustJoyful/ffmpeg-agent-ckpt-grpo --ckpt-dir /kaggle/working/grpo --steps 100
  ... + --shuffle-rewards 1 --steps 30 for the sanity control; + --resume after an interruption

Reads TRAIN tasks only (training.taskgen.loader purpose "grpo"). Never run without the owner's go-ahead (gate G3).
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig
from transformers import AutoTokenizer, TrainerCallback
from trl import GRPOConfig, GRPOTrainer

from training import config
from training.corpus.hub import pull_corpus, verify_corpus
from training.env.chat_template import install
from training.env.ffmpeg_pin import require_pinned
from training.env.ffmpeg_version import ffmpeg_version
from training.grpo.ckpt_sync import (
    SyncCallback,
    local_latest,
    remote_from_args,
    restore_latest,
    restore_metrics,
)
from training.grpo.gates import StopRules
from training.grpo.hf_batch import hf_batch_generator_for
from training.grpo.rollout import make_rollout_func, prompt_messages
from training.grpo.taskfilter import apply_filter
from training.grpo.telemetry import TelemetryLog, grpo_reward
from training.grpo.toy_spike import StepTimer
from training.precision import native_bf16, precision_plan
from training.sft.train import load_jsonl  # noqa: F401  (kept for symmetry with the SFT driver)
from training.taskgen.loader import load_extra_train, load_tasks
from training.teacher.generate import load_prompt_v1


class StopCallback(TrainerCallback):
    """Stops the Trainer when a preregistered rule fires or the GPU-hour cap is reached; records why."""

    def __init__(self, out: Path, max_gpu_hours: float):
        self.out, self.max_gpu_hours, self.reason, self.t0 = out, max_gpu_hours, None, time.time()

    def request(self, reason: str) -> None:
        self.reason = self.reason or reason

    def on_step_end(self, args, state, control, **kw):
        if self.reason is None and (time.time() - self.t0) / 3600 >= self.max_gpu_hours:
            self.reason = f"gpu_hour_cap:{self.max_gpu_hours}"
        if self.reason:
            control.should_training_stop = True
            (self.out / "stopped.json").write_text(
                json.dumps({"step": state.global_step, "reason": self.reason}) + "\n"
            )


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", required=True, help="merged SFT model dir or HF id")
    ap.add_argument("--ckpt-dir", type=Path, required=True)
    ap.add_argument("--steps", type=int, default=100)
    ap.add_argument("--num-generations", type=int, default=8)
    ap.add_argument("--prompts-per-step", type=int, default=8)
    ap.add_argument("--max-new-tokens", type=int, default=256)
    ap.add_argument("--max-runs", type=int, default=config.MAX_RUNS_PER_JOB)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--save-steps", type=int, default=10)
    ap.add_argument("--seed", type=int, default=config.TASKGEN_SEED)
    ap.add_argument("--precision", choices=["auto", "bf16", "fp16"], default="auto")
    ap.add_argument(
        "--pass-rates",
        type=Path,
        help="pass_rates.json from training.grpo.taskfilter (M1, train tasks only)",
    )
    ap.add_argument(
        "--extra-train",
        action="append",
        default=[],
        metavar="NAME",
        help="also train on data/tasks/train/NAME.jsonl (hash pinned in MANIFEST.json extra_train)",
    )
    ap.add_argument(
        "--pool-ids",
        type=Path,
        help="train task ids to train on, one per line (the reward-variance pool); every id must exist",
    )
    ap.add_argument(
        "--pass-rates-subset",
        action="store_true",
        help="the table measured only some train tasks: train on its in-band tasks, exclude the unmeasured ones",
    )
    ap.add_argument(
        "--corpus-repo", default=None, help="HF dataset repo with the hash-verified corpus tarball"
    )
    ap.add_argument("--hub-repo")
    ap.add_argument("--sync-dir", type=Path)
    ap.add_argument("--keep-last", type=int, default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument(
        "--shuffle-rewards", type=int, default=None, metavar="SEED", help="sanity control (T19)"
    )
    ap.add_argument(
        "--crash-after",
        type=int,
        default=None,
        help="test hook: hard-exit after checkpoint STEP is pushed",
    )
    ap.add_argument("--max-gpu-hours", type=float, default=config.GRPO_STOP_RULES["max_gpu_hours"])
    ap.add_argument("--allow-draft-prompt", action="store_true", help="smoke tests only")
    a = ap.parse_args(argv)
    if not torch.cuda.is_available():
        raise SystemExit("no CUDA GPU visible; refusing to run GRPO")
    require_pinned()  # fail closed on any other FFmpeg, and leave the evidence in the run log (G3 criterion d)
    print(
        f"ffmpeg pinned build verified: {ffmpeg_version(config.FFMPEG_BIN)} "
        f"(pinned {config.FFMPEG_PIN['version']})",
        flush=True,
    )

    prompt = load_prompt_v1(a.allow_draft_prompt)
    tasks = load_tasks("train", "grpo")
    for (
        name
    ) in a.extra_train:  # hash-pinned extra TRAIN files, e.g. hard-v1 (training.taskgen.register)
        tasks += load_extra_train(name, "grpo")
    assert len({t["id"] for t in tasks}) == len(tasks), "duplicate task ids across the train files"
    a.ckpt_dir.mkdir(parents=True, exist_ok=True)
    if a.pool_ids:
        wanted, by_id = a.pool_ids.read_text().split(), {t["id"]: t for t in tasks}
        if missing := [i for i in wanted if i not in by_id]:
            raise SystemExit(
                f"{len(missing)} pool ids are not in the train files, e.g. {missing[:3]}"
            )
        tasks = [by_id[i] for i in wanted]
        (a.ckpt_dir / "pool-ids.txt").write_text(
            a.pool_ids.read_text()
        )  # travels with the checkpoints
        digest = hashlib.sha256(a.pool_ids.read_bytes()).hexdigest()
        print(
            f"pool: {len(tasks)} train tasks from {a.pool_ids.name} (sha256 {digest})", flush=True
        )
    needed = {c for t in tasks for c in t["inputs"]}
    corpus = (
        pull_corpus(a.corpus_repo, config.CORPUS_DIR)
        if a.corpus_repo
        else verify_corpus(config.CORPUS_DIR, needed)
    )
    a.ckpt_dir.mkdir(parents=True, exist_ok=True)
    if a.pass_rates:
        tasks = apply_filter(tasks, a.pass_rates, a.ckpt_dir, subset=a.pass_rates_subset)
    tok = install(AutoTokenizer.from_pretrained(a.init))
    dataset = Dataset.from_list([{"prompt": prompt_messages(t, corpus, prompt)} for t in tasks])
    plan = precision_plan(a.precision, native_bf16())
    print(f"precision plan: {plan}; {len(tasks)} train tasks", flush=True)
    if not plan["mixed_out_gemm"]:
        import trl.kernels.chunked_logprob as chunked

        chunked._MM_OUT_DTYPE = False  # see training/precision.py

    args = GRPOConfig(
        output_dir=str(a.ckpt_dir), max_steps=a.steps, seed=a.seed, report_to="none", num_generations=a.num_generations,
        per_device_train_batch_size=a.num_generations, gradient_accumulation_steps=a.prompts_per_step,
        max_completion_length=a.max_runs * 2 * a.max_new_tokens + 2048, beta=0.0, learning_rate=a.lr, temperature=1.0,
        logging_steps=1, save_strategy="steps", save_steps=a.save_steps, save_total_limit=2,
        bf16=plan["bf16"], fp16=plan["fp16"], gradient_checkpointing=True, model_init_kwargs={"dtype": plan["model_dtype"]},
    )  # fmt: skip
    telemetry = TelemetryLog(a.ckpt_dir / "telemetry.jsonl", a.ckpt_dir / "spotcheck")
    gates, stop = StopRules(), StopCallback(a.ckpt_dir, a.max_gpu_hours)

    def on_rollout(step, records, episodes):
        row = telemetry.add(step, records, episodes)
        for rule in gates.update(row):
            stop.request(rule)

    rollout = make_rollout_func(
        tasks, corpus, None, jobs_root=config.JOBS_DIR / "grpo-main", max_new_tokens=a.max_new_tokens, max_runs=a.max_runs,
        reward_fn=grpo_reward, on_rollout=on_rollout, shuffle_seed=a.shuffle_rewards,
        batch_generator_for=hf_batch_generator_for(args.temperature), system_prompt_text=prompt, require_spec=True, stop_after_ask=True,
    )  # fmt: skip
    trainer = GRPOTrainer(
        model=a.init,
        args=args,
        train_dataset=dataset,
        rollout_func=rollout,
        processing_class=tok,
        reward_funcs=[lambda completions, reward, **kw: reward],
        peft_config=LoraConfig(
            r=16, lora_alpha=32, target_modules="all-linear", task_type="CAUSAL_LM"
        ),
    )
    metrics_path = a.ckpt_dir / "metrics.jsonl"
    trainer.add_callback(StepTimer(metrics_path, max(torch.cuda.device_count(), 1)))
    trainer.add_callback(stop)
    remote = remote_from_args(a.hub_repo, a.sync_dir, a.keep_last)
    if remote is not None:
        extras = [
            metrics_path,
            a.ckpt_dir / "telemetry.jsonl",
            a.ckpt_dir / "pass_rates.json",
            a.ckpt_dir / "stopped.json",
            a.ckpt_dir / "pool-ids.txt",
            a.ckpt_dir / "spotcheck",  # the top-reward transcripts the owner reviews
        ]
        trainer.add_callback(SyncCallback(remote, extras, a.crash_after))
    resume = None
    if a.resume:
        found = (
            restore_latest(remote, a.ckpt_dir) if remote is not None else local_latest(a.ckpt_dir)
        )
        if found is None:
            raise SystemExit(f"--resume given but no checkpoint in {a.ckpt_dir} or the remote")
        for name in ("metrics.jsonl", "telemetry.jsonl", "pass_rates.json"):
            restore_metrics(found, a.ckpt_dir, name)
        resume = str(found)
        print(f"resuming from {resume}", flush=True)
    trainer.train(resume_from_checkpoint=resume)


if __name__ == "__main__":
    main()
