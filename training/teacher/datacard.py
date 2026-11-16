"""Data card for a teacher run (RULES §5.4, §7.3): model id, date, terms snapshot, prices, seeds, family mix, cost.

A card with no terms URL/hash is marked INCOMPLETE: it documents what is missing instead of pretending (the owner
must confirm DeepSeek's terms allow training on outputs before bulk data is used, D-010)."""

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from training import config


def build_card(out_dir: Path, summary: dict) -> Path:
    kept = (
        [json.loads(x) for x in (out_dir / "kept.jsonl").read_text().splitlines()]
        if (out_dir / "kept.jsonl").exists()
        else []
    )
    fam = Counter("+".join(r["families"]) or "unsupported" for r in kept)
    missing = [
        name
        for name, val in (
            ("terms_url", config.TEACHER_TERMS_URL),
            ("terms_snapshot_sha256", config.TEACHER_TERMS_SNAPSHOT_SHA256),
        )
        if not val
    ]
    card = {
        "status": "INCOMPLETE: " + ", ".join(missing) if missing else "complete",
        "created": datetime.now(UTC).isoformat(),
        "teacher_model": config.DEEPSEEK_MODEL_ID,
        "prompt": config.SYSTEM_PROMPT_V1,
        "prompt_sha256": config.SYSTEM_PROMPT_V1_SHA256,
        "terms_url": config.TEACHER_TERMS_URL,
        "terms_snapshot_sha256": config.TEACHER_TERMS_SNAPSHOT_SHA256,
        "prices_usd_per_mtok": config.DEEPSEEK_PRICES_USD_PER_MTOK,
        "prices_checked": config.DEEPSEEK_PRICES_CHECKED,
        "taskgen_version": config.TASKGEN_VERSION,
        "taskgen_seed": config.TASKGEN_SEED,
        "kept_trajectories": len(kept),
        "kept_by_family": dict(sorted(fam.items())),
        "summary": summary,
        "filter": "only trajectories whose final outputs pass the checker against the gold spec are kept",
    }  # fmt: skip
    path = out_dir / "DATA_CARD.json"
    path.write_text(json.dumps(card, indent=1) + "\n")
    return path
