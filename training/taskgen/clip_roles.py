"""D-027(b): test-real clips must never be inputs of any other split. Used by the CI test and the build."""

import json
from pathlib import Path

from training import config


def real_clip_ids(manifest: Path = config.CORPUS_DIR / "manifest.json") -> set[str]:
    return {
        r["id"]
        for r in json.loads(manifest.read_text())
        if r.get("role", config.CLIP_ROLE_DEFAULT) == "test-real"
    }


def violations(tasks_root: Path, real: set[str]) -> list[tuple[str, str, str]]:
    """(file, task id, clip id) for every task outside test-real whose inputs include a test-real clip."""
    out = []
    for f in sorted(tasks_root.rglob("*.jsonl")):
        if f.relative_to(tasks_root).parts[0] == "test-real":
            continue
        for line in f.read_text().splitlines():
            t = json.loads(line)
            out += [(str(f), t["id"], c) for c in t["inputs"] if c in real]
    return out
