"""Preregistered GRPO stop rules (eval/PREREGISTRATION.md, Phase 1): a run that collapses should stop, not burn quota.

Fed one telemetry row per optimizer step (training/grpo/telemetry.summarize); returns the violated rules so the driver
can stop and the report can say why. Over-asking/over-refusing is the cheap, safe-looking action RL drifts towards.
"""

from dataclasses import dataclass, field

from training import config


@dataclass
class StopRules:
    rules: dict = field(default_factory=lambda: dict(config.GRPO_STOP_RULES))
    _no_signal: int = 0
    _refusal: int = 0
    _invalid_rising: int = 0
    _last_invalid: float | None = None

    def update(self, row: dict) -> list[str]:
        r, violated = self.rules, []
        self._no_signal = (
            self._no_signal + 1 if row["no_signal_group_share"] > r["no_signal_share"] else 0
        )
        self._refusal = (
            self._refusal + 1 if row["refusal_rate_on_supported"] > r["refusal_rate_max"] else 0
        )
        inv = row["invalid_action_rate"]
        self._invalid_rising = (
            self._invalid_rising + 1
            if self._last_invalid is not None and inv > self._last_invalid
            else 0
        )
        self._last_invalid = inv
        if self._no_signal >= r["no_signal_steps"]:
            violated.append("no_signal_groups")
        if self._refusal >= r["refusal_steps"]:
            violated.append("refusal_collapse")
        if self._invalid_rising >= r["invalid_rising_steps"]:
            violated.append("invalid_actions_rising")
        return violated
