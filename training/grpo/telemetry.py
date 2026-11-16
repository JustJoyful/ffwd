"""GRPO reward terms and per-step telemetry (T6; reward v1 DRAFT per ARCHITECTURE §7.4).

Rewards use the GOLD spec (RULES §4.4). Telemetry exists to spot a run that is not learning (groups
with no reward variance) or learning the wrong thing (reward hacking): it logs the term breakdown,
invalid-action rate, over-asking/over-refusing rates, and dumps the top-reward transcripts for hand
inspection every N steps. A shuffled-reward control can be switched on to show that gains vanish.
"""

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from training import config
from training.env.loop import Episode, score
from training.env.validator import uses_stream_copy_only


@dataclass
class RewardBreakdown:
    total: float
    terms: dict[str, float] = field(default_factory=dict)


def _flatten(node, prefix: str = "") -> dict[str, object]:
    """Non-null leaves of a spec as {path: value}; output lists are keyed by output id."""
    out: dict[str, object] = {}
    if isinstance(node, dict):
        for k, v in node.items():
            out.update(_flatten(v, f"{prefix}{k}."))
    elif isinstance(node, list):
        if node and all(isinstance(x, dict) and "id" in x for x in node):
            for x in node:
                out.update(
                    _flatten({k: v for k, v in x.items() if k != "id"}, f"{prefix}{x['id']}.")
                )
        else:
            out[prefix.rstrip(".")] = json.dumps(node, sort_keys=True)
    elif node is not None:
        out[prefix.rstrip(".")] = node
    return out


def spec_accuracy(emitted: dict | None, gold: dict | None) -> float:
    """Field-level F1 between the emitted spec and the gold spec (null fields ignored)."""
    if emitted is None or gold is None:
        return 0.0
    e, g = _flatten(emitted), _flatten(gold)
    if not e and not g:
        return 1.0
    hits = sum(1 for k, v in g.items() if e.get(k) == v)
    return 2 * hits / (len(e) + len(g))


def _partial(ep: Episode) -> float:
    if not ep.last_check:
        return 0.0
    checks = [c for o in ep.last_check["outputs"].values() for c in o.get("checks", [])]
    return sum(c["ok"] for c in checks) / len(checks) if checks else 0.0


def _needless_reencode(task: dict, ep: Episode) -> bool:
    refs = task.get("reference_runs")
    if not refs or not uses_stream_copy_only(refs[-1]["args"]):
        return False
    outs = (ep.last_check or {}).get("outputs", {})
    return any(o.get("measurements", {}).get("re_encoded") for o in outs.values())


def grpo_reward(
    task: dict, ep: Episode, weights: dict[str, float] | None = None
) -> RewardBreakdown:
    w = weights or config.REWARD_WEIGHTS
    flags = task["flags"]
    passed = score(task, ep)
    graded = not (flags["ambiguous"] or flags["unsupported"])
    clarify = 0.0
    if flags["ambiguous"]:
        clarify = 1.0 if ep.asked else 0.0
    elif flags["unsupported"]:
        clarify = 1.0 if (ep.refused and ep.runs == 0) else 0.0
    elif ep.asked or ep.refused:
        clarify = -1.0  # over-asking / over-refusing a supported task
    terms = {
        "pass": 1.0 if passed and graded else 0.0,
        "partial": 0.0 if passed else (_partial(ep) if graded else 0.0),
        "spec_acc": spec_accuracy(ep.emitted_spec, task.get("gold_spec")) if graded else 0.0,
        "efficiency": (
            0.0
            if not (passed and graded) or _needless_reencode(task, ep)
            else 1.0 / max(ep.runs, 1)
        ),
        "clarify": clarify,
        "invalid": float(min(ep.invalid_turns, config.REWARD_INVALID_CAP)),
    }
    return RewardBreakdown(sum(w[k] * v for k, v in terms.items()), terms)


def record_for(task: dict, ep: Episode, breakdown: RewardBreakdown, group: str) -> dict:
    """The flat per-rollout record the summaries are computed from."""
    return {
        "task_id": task["id"],
        "group": group,
        "total": breakdown.total,
        "terms": breakdown.terms,
        "invalid_turns": ep.invalid_turns,
        "turns": len(ep.turns),
        "runs": ep.runs,
        "supported": not (task["flags"]["ambiguous"] or task["flags"]["unsupported"]),
        "asked": ep.asked,
        "refused": ep.refused,
        "passed": score(task, ep),
    }


def summarize(records: list[dict], step: int) -> dict:
    n = len(records)
    groups: dict[str, list[float]] = defaultdict(list)
    for r in records:
        groups[r["group"]].append(r["total"])
    no_signal = sum(1 for rewards in groups.values() if max(rewards) - min(rewards) < 1e-12)
    totals = [r["total"] for r in records]
    mean = sum(totals) / n
    supported = [r for r in records if r["supported"]]
    turns = sum(r["turns"] for r in records)
    return {
        "step": step,
        "n_rollouts": n,
        "n_groups": len(groups),
        "no_signal_group_share": no_signal / len(groups),
        "mean_reward": mean,
        "reward_std": (sum((t - mean) ** 2 for t in totals) / n) ** 0.5,
        "terms_mean": {k: sum(r["terms"][k] for r in records) / n for k in records[0]["terms"]},
        "invalid_action_rate": sum(r["invalid_turns"] for r in records) / turns if turns else 0.0,
        "ask_rate_on_supported": (
            sum(r["asked"] for r in supported) / len(supported) if supported else 0.0
        ),
        "refusal_rate_on_supported": (
            sum(r["refused"] for r in supported) / len(supported) if supported else 0.0
        ),
        "runs_per_rollout": sum(r["runs"] for r in records) / n,
        "pass_rate": sum(r["passed"] for r in records) / n,
    }


class TelemetryLog:
    """Appends one summary row per step and dumps the top-reward transcripts every `every` steps."""

    def __init__(
        self,
        path: Path,
        spotcheck_dir: Path,
        every: int = config.TELEMETRY_SPOTCHECK_EVERY,
        top_k: int = config.TELEMETRY_SPOTCHECK_TOP_K,
    ):
        self.path, self.spotcheck_dir, self.every, self.top_k = (
            Path(path),
            Path(spotcheck_dir),
            every,
            top_k,
        )

    def add(self, step: int, records: list[dict], episodes: list[dict]) -> dict:
        row = summarize(records, step)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(row) + "\n")
        if self.every and step % self.every == 0:
            self.spotcheck_dir.mkdir(parents=True, exist_ok=True)
            best = sorted(zip(records, episodes, strict=True), key=lambda x: -x[0]["total"])[
                : self.top_k
            ]
            with (self.spotcheck_dir / f"step-{step}.jsonl").open("w") as f:
                for rec, e in best:
                    f.write(
                        json.dumps({"reward": rec["total"], "terms": rec["terms"], "episode": e})
                        + "\n"
                    )
        return row


def shuffle_within_groups(rewards: list[float], groups: list[str], seed: int) -> list[float]:
    """Sanity control: permute rewards inside each group. A run trained on these must NOT improve
    on dev; if it does, the gains come from something other than the reward signal."""
    rng = random.Random(seed)
    idx: dict[str, list[int]] = defaultdict(list)
    for i, g in enumerate(groups):
        idx[g].append(i)
    out = list(rewards)
    for members in idx.values():
        vals = [rewards[i] for i in members]
        rng.shuffle(vals)
        for i, v in zip(members, vals, strict=True):
            out[i] = v
    return out
