"""SFT data: kept trajectories -> masked token streams, mixed and capped (plan T16).

A stream is built by replaying the conversation through the SAME TokenPolicy the GRPO rollouts use
(training/env/chat_template.tokenize_with_mask), so SFT sees byte-for-byte what RL later generates; only assistant
actions and their <|im_end|> carry loss (labels = -100 elsewhere).
"""

import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from training import config
from training.env.chat_template import tokenize_with_mask

IGNORE = -100


def load_trajectories(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def family_key(rec: dict) -> str:
    return "+".join(rec["families"]) or "unsupported"


def drop_invalid_turns(messages: list[dict]) -> tuple[list[dict], int]:
    """Remove (assistant, observation) pairs whose observation is an `invalid action` error: the loss is on every
    assistant turn, so a schema-invalid turn the teacher later corrected would be learned. The state does not change
    after an invalid action, so the transcript stays coherent without the pair. Returns (messages, pairs dropped).
    """
    head, rest = messages[:2], messages[2:]
    out, dropped = list(head), 0
    for i in range(0, len(rest), 2):
        pair = rest[i : i + 2]
        try:
            err = json.loads(pair[1]["content"]).get("error", "") if len(pair) == 2 else ""
        except (ValueError, AttributeError):
            err = ""
        if isinstance(err, str) and err.startswith("invalid action"):
            dropped += 1
        else:
            out += pair
    return out, dropped


def build_examples(
    trajectories: list[dict], tokenizer, max_len: int = config.SFT_MAX_LEN
) -> tuple[list[dict], dict]:
    """[{task_id, family, input_ids, labels}], stats. Over-long streams are dropped AND counted (never silently)."""
    examples, dropped_long, dupes, seen, invalid_pairs = [], 0, 0, set(), 0
    for rec in trajectories:
        rec = rec | dict(zip(("messages", "_n"), drop_invalid_turns(rec["messages"]), strict=True))
        invalid_pairs += rec.pop("_n")
        digest = hashlib.sha256(json.dumps(rec["messages"], sort_keys=True).encode()).hexdigest()
        if digest in seen:
            dupes += 1
            continue
        seen.add(digest)
        ids, mask = tokenize_with_mask(rec["messages"], tokenizer)
        if len(ids) > max_len:
            dropped_long += 1
            continue
        labels = [t if m else IGNORE for t, m in zip(ids, mask, strict=True)]
        examples.append(
            {
                "task_id": rec["task_id"],
                "family": family_key(rec),
                "input_ids": ids,
                "labels": labels,
            }
        )
    return examples, {
        "kept": len(examples),
        "dropped_too_long": dropped_long,
        "duplicates": dupes,
        "invalid_turn_pairs_removed": invalid_pairs,
        "max_len": max_len,
    }


def mix(
    teacher: list[dict],
    rejection: list[dict],
    *,
    oracle: list[dict] | None = None,
    oracle_share_max: float | None = config.SFT_ORACLE_SHARE_MAX,
    per_family_cap: float = config.SFT_FAMILY_CAP,
    rejection_share_max: float = config.SFT_REJECTION_SHARE_MAX,
    seed: int = config.TASKGEN_SEED,
) -> list[dict]:
    """Teacher data, plus base-model rejection samples and programmatic oracle trajectories (D-032), each capped at
    a share of the final mix, with no family above `per_family_cap` of it (a family over the cap is subsampled,
    deterministically). Oracle examples carry source="oracle" (data card). `oracle_share_max=None` lifts the oracle
    cap: only for the explicit fallback when the teacher budget is gone, or the M1-oracle ablation (teacher=[]).
    """
    rng = random.Random(seed)
    pool = [{**e, "source": e.get("source", "teacher")} for e in teacher]
    r = list(rejection)
    rng.shuffle(r)
    max_rej = int(rejection_share_max * len(teacher) / (1 - rejection_share_max)) if teacher else 0
    pool += [{**e, "source": "rejection"} for e in r[:max_rej]]
    o = list(oracle or [])
    rng.shuffle(o)
    if oracle_share_max is not None:
        o = o[: int(oracle_share_max * len(pool) / (1 - oracle_share_max))] if pool else []
    pool += [{**e, "source": "oracle"} for e in o]
    by_fam = defaultdict(list)
    for ex in pool:
        by_fam[ex["family"]].append(ex)
    cap = max(1, int(per_family_cap * len(pool)))
    out = []
    for fam in sorted(by_fam):
        items = sorted(by_fam[fam], key=lambda e: e["task_id"])
        if len(items) > cap:
            rng_f = random.Random(f"{seed}:{fam}")
            items = rng_f.sample(items, cap)
        out += items
    return sorted(out, key=lambda e: e["task_id"])


def validation_split(
    examples: list[dict], content_keys: dict[str, str], fraction: float = 0.05
) -> tuple[list[dict], list[dict]]:
    """Hold out whole CONTENTS (not single wordings) from the train data, so validation loss is not inflated by
    paraphrases of trained tasks. Uses train content keys only (no dev/test)."""

    def held(ex):
        return (
            int(hashlib.sha256(content_keys[ex["task_id"]].encode()).hexdigest(), 16) % 1000
            < fraction * 1000
        )

    val = [e for e in examples if held(e)]
    return [e for e in examples if not held(e)], val


def stats(examples: list[dict]) -> dict:
    lens = [len(e["input_ids"]) for e in examples]
    trained = sum(1 for e in examples for x in e["labels"] if x != IGNORE)
    return {
        "examples": len(examples), "mean_len": round(sum(lens) / max(1, len(lens)), 1), "max_len": max(lens, default=0),
        "by_source": dict(sorted(Counter(e.get("source", "teacher") for e in examples).items())),
        "trained_tokens": trained, "by_family": dict(sorted(Counter(e["family"] for e in examples).items())),
    }  # fmt: skip
