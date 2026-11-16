"""TRL `rollout_func` for multi-turn GRPO (D-018). Torch-free: generation is injected.

One episode = ONE exact token stream: prompt_ids, then for each turn the model's sampled tokens
(env_mask 1, their sampling logprobs) followed by the observation we insert (env_mask 0, logprob 0,
excluded from the loss). Generation always continues from that stream, never from a re-rendered
chat template, so what we train on is exactly what was sampled.
Known gap: at inference the chat template re-renders history without the empty <think> blocks.
"""

import dataclasses
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from training import config
from training.env.loop import Episode, initial_messages, run_episode, score
from training.env.probe import probe
from training.grpo.telemetry import RewardBreakdown, record_for, shuffle_within_groups


class Generator(Protocol):
    def __call__(self, ids: list[int], max_new_tokens: int) -> tuple[list[int], list[float]]: ...


class TokenPolicy:
    """A loop Policy that records the token stream it generates and the observations it is fed."""

    def __init__(self, tokenizer, generate: Generator, max_new_tokens: int):
        self.tok, self.generate, self.max_new_tokens = tokenizer, generate, max_new_tokens
        self.im_end = tokenizer.convert_tokens_to_ids("<|im_end|>")
        self.prompt_ids: list[int] | None = None
        self.completion_ids: list[int] = []
        self.env_mask: list[int] = []
        self.logprobs: list[float] = []

    def _append(self, ids: list[int], mask: int, logprobs: list[float] | None = None) -> None:
        self.completion_ids += ids
        self.env_mask += [mask] * len(ids)
        self.logprobs += logprobs if logprobs is not None else [0.0] * len(ids)

    def __call__(self, messages: list[dict]) -> str:
        if self.prompt_ids is None:
            ids = self.tok.apply_chat_template(
                messages, add_generation_prompt=True, enable_thinking=False, tokenize=True
            )
            # transformers ≥5 returns a BatchEncoding; older versions a plain list
            self.prompt_ids = list(ids["input_ids"] if hasattr(ids, "keys") else ids)
        else:
            if not self.completion_ids or self.completion_ids[-1] != self.im_end:
                self._append([self.im_end], 0)  # truncated turn: close it, but don't train on it
            obs = config.QWEN3_OBSERVATION_TEMPLATE.format(obs=messages[-1]["content"])
            self._append(self.tok.encode(obs, add_special_tokens=False), 0)
        ids, lps = self.generate(self.prompt_ids + self.completion_ids, self.max_new_tokens)
        self._append(list(ids), 1, list(lps))
        return self.tok.decode(ids, skip_special_tokens=True)

    def trajectory(self) -> dict:
        return {
            "prompt_ids": self.prompt_ids or [],
            "completion_ids": self.completion_ids,
            "env_mask": self.env_mask,
            "logprobs": self.logprobs,
        }


def toy_reward(task: dict, ep: Episode) -> float:
    """Phase 0 toy reward only (the real reward v1 is Phase 1, ARCH §7.4)."""
    return (1.0 if score(task, ep) else 0.0) - 0.5 * ep.invalid_turns


def prompt_messages(task: dict, corpus: dict[str, Path]) -> list[dict]:
    return initial_messages(task, {cid: probe(corpus[cid]) for cid in task["inputs"]})


def make_rollout_func(
    tasks: list[dict],
    corpus: dict[str, Path],
    generator_for: Callable[[object], Generator],
    *,
    jobs_root: Path,
    max_new_tokens: int,
    max_runs: int = config.MAX_RUNS_PER_JOB,
    reward_fn: Callable[[dict, Episode], RewardBreakdown] | None = None,
    on_rollout: Callable[[int, list[dict], list[dict]], None] | None = None,
    shuffle_seed: int | None = None,
):
    """rollout_func(prompts, trainer) for GRPOTrainer. Prompts are matched to tasks by their
    first user message (request + probes), which is unique per task.

    reward_fn: per-episode reward (default: the Phase 0 toy reward). on_rollout(step, records, episodes)
    gets one flat record and one transcript per rollout, for telemetry. shuffle_seed switches on the
    shuffled-reward sanity control: rewards are permuted within each prompt's group before training,
    while the telemetry still logs the TRUE rewards.
    """
    by_key = {prompt_messages(t, corpus)[-1]["content"]: t for t in tasks}
    reward_fn = reward_fn or (
        lambda task, ep: RewardBreakdown(toy_reward(task, ep), {"pass": float(score(task, ep))})
    )

    def rollout_func(prompts: list[list[dict]], trainer) -> dict:
        generate = generator_for(trainer)
        out: dict[str, list] = {
            k: [] for k in ("prompt_ids", "completion_ids", "logprobs", "env_mask")
        }
        step = getattr(getattr(trainer, "state", None), "global_step", 0) + 1
        records, episodes = [], []
        for prompt in prompts:
            task = by_key[prompt[-1]["content"]]
            policy = TokenPolicy(trainer.processing_class, generate, max_new_tokens)
            ep = run_episode(
                task,
                policy,
                corpus=corpus,
                job_dir=jobs_root / uuid.uuid4().hex,
                max_runs=max_runs,
                run_timeout_s=config.ROLLOUT_RUN_TIMEOUT_S,
                max_output_bytes=config.ROLLOUT_MAX_OUTPUT_BYTES,
            )
            for k, v in policy.trajectory().items():
                out[k].append(v)
            records.append(record_for(task, ep, reward_fn(task, ep), f"{step}:{task['id']}"))
            episodes.append(dataclasses.asdict(ep))
        trained = [r["total"] for r in records]
        if shuffle_seed is not None:
            trained = shuffle_within_groups(
                trained, [r["group"] for r in records], shuffle_seed + step
            )
        out["reward"] = trained
        out["toy_reward"] = trained  # name used by the Phase 0 toy reward function
        if on_rollout is not None:
            on_rollout(step, records, episodes)
        return out

    return rollout_func
