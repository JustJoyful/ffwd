"""Register a hard-variant pool (training.taskgen.hard) as an extra TRAIN file with its own hash in MANIFEST.json.

uv run python -m training.taskgen.register --pool data/tasks-hard/widened-pilot --name hard-v1

Writes data/tasks/train/<name>.jsonl (byte-identical to the pool's tasks.jsonl) and pins its sha256 under
MANIFEST.json["extra_train"][name]; `training.taskgen.loader.load_extra_train` verifies it on every read. The existing
`splits` entries of MANIFEST.json are not touched. Checks, all of which must hold or nothing is written:
* every task is split "train", rendered in a TRAIN style only (never a held-out style), ids and content keys unique;
* `assign_split(content_key, families)` is "train" for every task (so it cannot be in dev, test-iid, test-phrasing by
  hash bucket, nor in a held-out family combination = test-compositional);
* no content key appears in train/v1 or dev/v1 (the only other files read; no test file is opened).
Regenerating the splits with training.taskgen.build rewrites MANIFEST.json and drops this entry (that rebuild would
change every split anyway, D-033): register the pool again afterwards.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from training import config
from training.taskgen import phrasing
from training.taskgen.splits import assign_split


def _keys(path: Path) -> set[str]:
    return {json.loads(x)["content_key"] for x in path.read_text().splitlines() if x.strip()}


def register(pool_dir: Path, name: str, tasks_root: Path | None = None) -> dict:
    root = tasks_root or config.DATA_DIR / "tasks"
    dest = root / "train" / f"{name}.jsonl"
    if dest.exists():
        raise FileExistsError(f"{dest} exists: pools are never overwritten")
    blob = (pool_dir / "tasks.jsonl").read_bytes()
    tasks = [json.loads(x) for x in blob.decode().splitlines() if x.strip()]
    ids, keys = [t["id"] for t in tasks], [t["content_key"] for t in tasks]
    problems = []
    if any(t["split"] != "train" for t in tasks):
        problems.append("a task is not labelled split=train")
    if {t["style"] for t in tasks} - set(phrasing.TRAIN_STYLES):
        problems.append("a task uses a style outside phrasing.TRAIN_STYLES")
    if len(set(ids)) != len(ids) or len(set(keys)) != len(keys):
        problems.append("duplicate task ids or content keys")
    if any(
        assign_split(t["content_key"], t["families"], config.TASKGEN_SEED) != "train" for t in tasks
    ):
        problems.append("a task does not hash to the train split (or is a held-out combination)")
    overlap = set(keys) & (_keys(root / "train" / "v1.jsonl") | _keys(root / "dev" / "v1.jsonl"))
    if overlap:
        problems.append(f"{len(overlap)} content keys already in train/v1 or dev/v1")
    if problems:
        raise ValueError("; ".join(problems))
    manifest_path = root / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    if name in manifest.get("extra_train", {}):
        raise FileExistsError(f"MANIFEST.json already pins extra_train/{name}")
    pool_manifest = (pool_dir / "manifest.json").read_bytes()
    entry = {
        "file": f"train/{name}.jsonl",
        "sha256": hashlib.sha256(blob).hexdigest(),
        "tasks": len(tasks),
        "pool_manifest_sha256": hashlib.sha256(pool_manifest).hexdigest(),
        "generator": json.loads(pool_manifest).get("generator_version"),
        "family_count": {  # string keys: what the JSON round trip gives anyway
            str(k): v for k, v in sorted(Counter(len(t["families"]) for t in tasks).items())
        },
        "styles": dict(sorted(Counter(t["style"] for t in tasks).items())),
    }
    dest.write_bytes(blob)
    manifest.setdefault("extra_train", {})[name] = entry
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return entry


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", type=Path, required=True, help="dir with tasks.jsonl + manifest.json")
    ap.add_argument("--name", required=True)
    a = ap.parse_args()
    print(json.dumps(register(a.pool, a.name), indent=1))


if __name__ == "__main__":
    main()
