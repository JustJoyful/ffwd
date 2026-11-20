"""Counts of copy-eligible tasks per test split (owner approval, 20 Nov 2026: "Exact test counts: yes ... copy-eligible flags
only, no outcomes"). For the power section of the M3 preregistration draft.

uv run python -m eval.copy_eligible_counts --out reports/<date>-test-counts

Reads the test task files through the guarded loader (`load_tasks(split, "test-eval")`, the ONLY purpose that may open them)
and keeps three integers per split: tasks, graded (not ambiguous, not unsupported, has a reference run) and copy-eligible
(graded and the reference run is stream-copy only). It also counts copy-eligible tasks inside the deduplicated test-iid
subset of D-039 (ids from the leakage audit). It never prints or stores a task id, request, command or any outcome, and it
runs no system. The run is logged: file hashes, commit, UTC time.
"""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from training import config
from training.env.validator import uses_stream_copy_only
from training.taskgen.loader import load_tasks, tasks_path

DEDUP = config.DATA_DIR.parent / "reports" / "2026-11-20-leakage-audit" / "exact-duplicates.json"


def graded(t: dict) -> bool:
    return not (t["flags"]["ambiguous"] or t["flags"]["unsupported"]) and bool(t["reference_runs"])


def copy_eligible(t: dict) -> bool:
    return graded(t) and uses_stream_copy_only(t["reference_runs"][-1]["args"])


def counts(tasks: list[dict], only_ids: set[str] | None = None) -> dict:
    ts = [t for t in tasks if only_ids is None or t["id"] in only_ids]
    return {
        "tasks": len(ts),
        "graded": sum(graded(t) for t in ts),
        "copy_eligible": sum(copy_eligible(t) for t in ts),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    per_split, hashes = {}, {}
    for split in config.TEST_SPLITS:
        if not tasks_path(split, "v1").exists():
            continue  # test-real has no task file yet
        tasks = load_tasks(split, "test-eval")
        per_split[split] = counts(tasks)
        hashes[split] = hashlib.sha256(tasks_path(split, "v1").read_bytes()).hexdigest()
        if split == "test-iid" and DEDUP.exists():
            dedup = set(json.loads(DEDUP.read_text())["test-iid"]["dedup_ids"])
            per_split["test-iid-dedup"] = counts(tasks, dedup)
    pooled = {
        k: per_split["test-iid"][k] + per_split["test-phrasing"][k]
        for k in ("tasks", "graded", "copy_eligible")
    }
    a.out.mkdir(parents=True)
    out = {"per_split": per_split, "q3a_pooled_test_iid_plus_phrasing": pooled}
    (a.out / "counts.json").write_text(json.dumps(out, indent=1) + "\n")
    manifest = {
        "report": "test-counts",
        "purpose": "copy-eligible counts per test split, for the M3 preregistration draft power section",
        "approval": "owner, 20 Nov 2026: exact test counts, copy-eligible flags only, no outcomes",
        "reader": 'training.taskgen.loader.load_tasks(split, "test-eval"); no task id, request, command or outcome kept or printed',
        "task_file_sha256": hashes,
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "systems_run": [],
    }
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
