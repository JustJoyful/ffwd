"""Rejection sampling from a FREE local model (plan T15): sample the base Qwen3 N times on EASY train tasks and keep the
runs that pass the checker. Cheap regularisation and a fallback if teacher budget runs short; capped in the SFT mix
(training.sft.dataset.mix) because base-model successes are easy, low-information and in the model's own style.
"""

import hashlib
import json
import uuid
from collections.abc import Callable
from pathlib import Path

from training.env.loop import Policy, run_episode, score
from training.teacher.generate import load_prompt_v1, make_record


def rejection_sample(
    tasks: list[dict],
    policy_factory: Callable[[], Policy],
    corpus: dict[str, Path],
    out_dir: Path,
    *,
    n: int = 8,
    max_difficulty: int = 1,
    allow_draft_prompt: bool = False,
) -> dict:
    if any(t["split"] != "train" for t in tasks):
        raise PermissionError("rejection sampling reads train tasks only (RULES §4.5)")
    prompt = load_prompt_v1(allow_draft_prompt)
    out_dir.mkdir(parents=True, exist_ok=True)
    kept_path, seen, attempted, kept = out_dir / "kept.jsonl", set(), 0, 0
    for task in tasks:
        if task["difficulty"] > max_difficulty:
            continue
        for _ in range(n):
            ep = run_episode(
                task, policy_factory(), corpus=corpus, job_dir=out_dir / "jobs" / uuid.uuid4().hex,
                system_prompt_text=prompt, require_spec=True, stop_after_ask=True,
            )  # fmt: skip
            attempted += 1
            if not score(task, ep):
                continue
            rec = make_record(task, ep, corpus, prompt, True, 0.0)
            digest = hashlib.sha256(
                json.dumps(rec["messages"], sort_keys=True).encode()
            ).hexdigest()
            if digest in seen:  # identical transcripts add nothing
                continue
            seen.add(digest)
            kept += 1
            with kept_path.open("a") as f:
                f.write(json.dumps(rec) + "\n")
    return {"attempted": attempted, "kept": kept, "distinct": len(seen)}
