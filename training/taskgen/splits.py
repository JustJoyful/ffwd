"""Split assignment by CONTENT hash (D-027): every wording/style of one task shares its content key, so a task
can never be in train while a paraphrase of it sits in a test split."""

import hashlib

from training import config


def bucket(content_key: str, seed: int = config.TASKGEN_SEED) -> int:
    return int(hashlib.sha256(f"{seed}:{content_key}".encode()).hexdigest(), 16) % 100


def is_heldout_combo(families: list[str]) -> bool:
    return tuple(sorted(families, key=lambda f: int(f[1:]))) in {
        tuple(sorted(c, key=lambda f: int(f[1:]))) for c in config.HELDOUT_COMBOS
    }


def assign_split(content_key: str, families: list[str], seed: int = config.TASKGEN_SEED) -> str:
    """train | dev | test-iid | test-compositional | test-phrasing (the last: contents rendered in held-out styles)."""
    if is_heldout_combo(families):
        return "test-compositional"
    b = bucket(content_key, seed)
    t_train, t_dev, t_iid = config.SPLIT_BUCKETS
    return (
        "train"
        if b < t_train
        else "dev" if b < t_dev else "test-iid" if b < t_iid else "test-phrasing"
    )
