"""The only sanctioned way for training code to read tasks (RULES §4.5: test data is sacred).

Every reader states its PURPOSE; the purpose decides which splits it may open (config.SPLIT_PURPOSES).
A teacher run, SFT, GRPO or any tuning step can therefore never read a test split by accident: asking
raises SplitAccessError before any file is opened. Only purpose "test-eval" reads test splits, and the
final test run additionally goes through eval/testlock.py.
"""

import json
from pathlib import Path

from training import config


class SplitAccessError(PermissionError):
    pass


def tasks_path(split: str, version: str) -> Path:
    return config.DATA_DIR / "tasks" / split / f"{version}.jsonl"


def load_tasks(split: str, purpose: str, *, version: str = "v1") -> list[dict]:
    allowed = config.SPLIT_PURPOSES.get(purpose)
    if allowed is None:
        raise SplitAccessError(
            f"unknown purpose {purpose!r}; known: {sorted(config.SPLIT_PURPOSES)}"
        )
    if split not in allowed:
        raise SplitAccessError(
            f"purpose {purpose!r} may not read split {split!r} (allowed: {allowed})"
        )
    tasks = [
        json.loads(x) for x in tasks_path(split, version).read_text().splitlines() if x.strip()
    ]
    wrong = sorted({t["split"] for t in tasks} - {split})
    if wrong:  # a mislabelled file would otherwise smuggle test tasks past the guard
        raise SplitAccessError(f"{tasks_path(split, version).name} contains tasks labelled {wrong}")
    return tasks
