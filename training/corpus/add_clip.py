"""Register one extra clip (e.g. the owner's own recording) in the corpus manifest.

uv run python -m training.corpus.add_clip ~/Videos/trip.mp4 --id trip_phone \
    --licence "own recording, CC0" --source "owner, Pixel 8" --role taskgen

Every clip needs a role (D-027b): `test-real` clips are held out BY CLIP from all generated tasks.
Copies the file into data/corpus, records sha256 + probe + licence (RULES §7.5: record the licence BEFORE
use; an empty licence is refused). Media stays untracked; only the manifest is committed. Real clips are
not regenerable: Phase 1 distributes them through a private Hugging Face dataset (plan T3).
"""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from training import config
from training.env.probe import probe


def add_clip(
    src: Path,
    clip_id: str,
    licence: str,
    source: str,
    role: str,
    corpus_dir: Path = config.CORPUS_DIR,
    *,
    tags: tuple[str, ...] = (),
    known_offset_ms: float | None = None,
    extra: dict | None = None,
) -> dict:
    if role not in config.CLIP_ROLES:
        raise ValueError(
            f"role must be one of {config.CLIP_ROLES} (D-027b): decide per clip, no default"
        )
    if not licence.strip():
        raise ValueError("a licence statement is required (RULES §7.5)")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,15}", clip_id):
        raise ValueError("clip id must match ^[a-z][a-z0-9_]{0,15}$ (spec id pattern)")
    manifest = corpus_dir / "manifest.json"
    records = json.loads(manifest.read_text())
    if any(r["id"] == clip_id for r in records):
        raise ValueError(f"clip id {clip_id!r} already exists")
    dest = corpus_dir / f"{clip_id}{src.suffix.lower()}"
    shutil.copy2(src, dest)
    record = {
        "id": clip_id,
        "file": dest.name,
        "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        "licence": licence,
        "source": source,
        "role": role,
        "probe": probe(dest),
        "tags": list(tags),
        "known_offset_ms": known_offset_ms,
        **(extra or {}),
    }
    manifest.write_text(json.dumps([*records, record], indent=2) + "\n")
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--id", required=True)
    ap.add_argument("--licence", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--role", required=True, choices=config.CLIP_ROLES,
                    help="taskgen: may feed generated tasks; test-real: only the hand-written test-real tasks")  # fmt: skip
    a = ap.parse_args()
    rec = add_clip(a.path, a.id, a.licence, a.source, a.role)
    print(json.dumps({k: rec[k] for k in ("id", "file", "sha256", "licence")}, indent=2))


if __name__ == "__main__":
    main()
