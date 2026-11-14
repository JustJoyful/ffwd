"""Budget guard for every paid API call (RULES §5.1).

Append-only JSONL ledger. Before a call we RESERVE its worst-case cost; after it we SETTLE the
actual cost. A reservation that is never settled (crash, timeout, exception) keeps counting at its
full reserved value forever, so a dying process can never make the ledger under-count spend.
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from training import config


class BudgetExceeded(RuntimeError):
    pass


class BudgetConfigError(RuntimeError):
    pass


def require_pricing() -> None:
    prices = config.DEEPSEEK_PRICES_USD_PER_MTOK
    tiers_ok = all(v is not None for tier in prices.values() for v in tier.values())
    if not (tiers_ok and config.DEEPSEEK_PRICES_CHECKED and config.DEEPSEEK_MODEL_ID):
        raise BudgetConfigError(
            "Set DEEPSEEK_PRICES_USD_PER_MTOK, DEEPSEEK_PRICES_CHECKED and DEEPSEEK_MODEL_ID in "
            "training/config.py from the official pricing page before any paid call."
        )


def billing_prices() -> dict:
    # shortcut: always bill at PEAK rates (≤2× real off-peak cost) because we don't encode the
    # off-peak window; upgrade by adding the window to config once the owner confirms it.
    return config.DEEPSEEK_PRICES_USD_PER_MTOK["peak"]


def cost_from_usage(usage: dict, prices: dict) -> float:
    hit = usage.get("prompt_cache_hit_tokens") or 0
    miss = usage.get("prompt_cache_miss_tokens")
    if miss is None:  # provider without cache accounting: treat every prompt token as a miss
        miss = (usage.get("prompt_tokens") or 0) - hit
    out = usage.get("completion_tokens") or 0
    return (
        hit * prices["input_cache_hit"] + miss * prices["input_cache_miss"] + out * prices["output"]
    ) / 1e6


def worst_case_cost(prompt_tokens_est: int, max_output_tokens: int, prices: dict) -> float:
    return (
        prompt_tokens_est * prices["input_cache_miss"] + max_output_tokens * prices["output"]
    ) / 1e6


class BudgetGuard:
    def __init__(
        self,
        ledger: Path,
        lifetime_cap_usd: float,
        run_cap_usd: float,
        run_id: str,
        dry_run: bool = False,
    ):
        self.ledger, self.lifetime_cap, self.run_cap = ledger, lifetime_cap_usd, run_cap_usd
        self.run_id, self.dry_run = run_id, dry_run

    def _records(self) -> list[dict]:
        if not self.ledger.exists():
            return []
        return [json.loads(line) for line in self.ledger.read_text().splitlines() if line.strip()]

    def _append(self, rec: dict) -> None:
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a") as f:
            f.write(
                json.dumps({"ts": datetime.now(UTC).isoformat(), "run_id": self.run_id, **rec})
                + "\n"
            )
            f.flush()

    def spent(self, run_only: bool = False) -> float:
        reserved: dict[str, tuple[str, float]] = {}
        settled: dict[str, float] = {}
        for r in self._records():
            if r["kind"] == "reserve":
                reserved[r["reservation_id"]] = (r["run_id"], r["cost_usd"])
            else:
                settled[r["reservation_id"]] = r["cost_usd"]
        return sum(
            settled.get(rid, cost)
            for rid, (run, cost) in reserved.items()
            if not run_only or run == self.run_id
        )

    def reserve(self, max_cost_usd: float) -> str:
        if self.spent() + max_cost_usd > self.lifetime_cap:
            raise BudgetExceeded(f"lifetime cap ${self.lifetime_cap:.2f} would be exceeded")
        if self.spent(run_only=True) + max_cost_usd > self.run_cap:
            raise BudgetExceeded(f"run cap ${self.run_cap:.2f} would be exceeded")
        rid = uuid.uuid4().hex
        if not self.dry_run:
            self._append({"kind": "reserve", "reservation_id": rid, "cost_usd": max_cost_usd})
        return rid

    def settle(self, reservation_id: str, usage: dict, cost_usd: float) -> None:
        if self.dry_run:
            return
        self._append(
            {
                "kind": "settle",
                "reservation_id": reservation_id,
                "cost_usd": cost_usd,
                "prompt_cache_hit_tokens": usage.get("prompt_cache_hit_tokens"),
                "prompt_cache_miss_tokens": usage.get("prompt_cache_miss_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            }
        )

    def cache_hit_ratio(self) -> float:
        hit = miss = 0
        for r in self._records():
            if r["kind"] == "settle" and r["run_id"] == self.run_id:
                hit += r.get("prompt_cache_hit_tokens") or 0
                miss += r.get("prompt_cache_miss_tokens") or 0
        return hit / (hit + miss) if hit + miss else 0.0
