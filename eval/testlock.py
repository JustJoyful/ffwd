"""Single-shot guard for the held-out test splits (D-030, RULES §4.5/§4.6).

A (system, checkpoint, split) triple can be evaluated on a test split ONCE. Locking happens BEFORE the run
starts, so a crash or an unflattering first result cannot be quietly retried; a deliberate re-run needs a written
reason and is logged as such. Test runs are also refused unless eval/PREREGISTRATION.md says "Phase 1 status: FINAL".
"""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from training import config

LEDGER = config.REPO_ROOT / "reports" / "TEST_RUNS.jsonl"
PREREG = config.REPO_ROOT / "eval" / "PREREGISTRATION.md"


class TestAlreadyRun(RuntimeError):
    __test__ = False  # not a pytest class


class NotPreregistered(RuntimeError):
    pass


def _records(ledger: Path) -> list[dict]:
    return [json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []


def acquire_test_run(
    system: str,
    checkpoint: str,
    split: str,
    *,
    ledger: Path = LEDGER,
    prereg: Path = PREREG,
    supersede_reason: str | None = None,
) -> None:
    """No-op for non-test splits. Raises NotPreregistered / TestAlreadyRun; otherwise records the lock."""
    if split not in config.TEST_SPLITS:
        return
    if system.startswith(config.DEV_ONLY_SYSTEM_PREFIXES):
        raise PermissionError(
            f"{system} is a dev-only ablation (D-032): it is never run on a test split"
        )
    if not prereg.exists() or "Phase 1 status: FINAL" not in prereg.read_text():
        raise NotPreregistered(
            "eval/PREREGISTRATION.md must say 'Phase 1 status: FINAL' before any test run"
        )
    prior = [
        r
        for r in _records(ledger)
        if (r["system"], r["checkpoint"], r["split"]) == (system, checkpoint, split)
    ]
    if prior and not (supersede_reason or "").strip():
        raise TestAlreadyRun(
            f"{system}/{checkpoint} was already run on {split} at {prior[-1]['ts']}; pass a supersede reason to re-run"
        )
    ledger.parent.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    rec = {
        "ts": datetime.now(UTC).isoformat(),
        "system": system,
        "checkpoint": checkpoint,
        "split": split,
        "git_commit": commit,
    }
    if prior:
        rec["superseded"], rec["supersede_reason"] = True, supersede_reason
    with ledger.open("a") as f:
        f.write(json.dumps(rec) + "\n")
