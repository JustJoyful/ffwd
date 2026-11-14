"""One OpenAI-compatible chat policy for every system: llama-server/vLLM for Qwen3 (free, local)
and the DeepSeek API (paid, always behind a BudgetGuard)."""

import json
import os
import tomllib
from pathlib import Path

from openai import OpenAI

from training import config
from training.teacher.budget import (
    BudgetGuard,
    billing_prices,
    cost_from_usage,
    require_pricing,
    worst_case_cost,
)

DRY_RUN_REPLY = '{"action": "unsupported", "reason": "dry run: no API call made"}'


def estimate_prompt_tokens(messages: list[dict]) -> int:
    # shortcut: ~3 chars/token over-estimates for JSON-heavy prompts; settle uses real usage.
    return len(json.dumps(messages)) // 3 + 1


class ChatPolicy:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key_env: str | None,
        *,
        temperature: float = 0.0,
        max_tokens: int,
        extra_body: dict | None = None,
        guard: BudgetGuard | None = None,
    ):
        if guard is not None:
            require_pricing()
        self.model, self.temperature, self.max_tokens = model, temperature, max_tokens
        self.extra_body, self.guard = extra_body, guard
        key = os.environ.get(api_key_env, "") if api_key_env else "not-needed"
        self._client = OpenAI(base_url=base_url, api_key=key or "missing")

    def __call__(self, messages: list[dict]) -> str:
        rid = None
        if self.guard is not None:
            prices = billing_prices()
            rid = self.guard.reserve(
                worst_case_cost(estimate_prompt_tokens(messages), self.max_tokens, prices)
            )
            if self.guard.dry_run:
                return DRY_RUN_REPLY
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            extra_body=self.extra_body,
        )
        if self.guard is not None:
            usage = resp.usage.model_dump() if resp.usage else {}
            self.guard.settle(rid, usage, cost_from_usage(usage, billing_prices()))
        return resp.choices[0].message.content or ""


def policy_from_config(path: Path, guard: BudgetGuard | None) -> ChatPolicy:
    cfg = tomllib.loads(path.read_text())
    if cfg.get("paid"):
        if guard is None:
            raise ValueError(f"{path.name} is a paid model: a BudgetGuard is required")
        return ChatPolicy(
            config.DEEPSEEK_BASE_URL,
            config.DEEPSEEK_MODEL_ID or "",
            config.DEEPSEEK_API_KEY_ENV,
            temperature=cfg.get("temperature", 0.0),
            max_tokens=config.TEACHER_MAX_OUTPUT_TOKENS,
            extra_body=cfg.get("extra_body"),
            guard=guard,
        )
    return ChatPolicy(
        cfg["base_url"],
        cfg["model"],
        cfg.get("api_key_env"),
        temperature=cfg.get("temperature", 0.0),
        max_tokens=cfg["max_tokens"],
        extra_body=cfg.get("extra_body"),
        guard=None,
    )
