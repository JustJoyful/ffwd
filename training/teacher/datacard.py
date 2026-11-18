"""Data card for a teacher run (RULES §5.4, §7.3): model id, date, terms snapshot, prices, seeds, family mix, cost.

A card with no terms URL/hash is marked INCOMPLETE: it documents what is missing instead of pretending (the owner
must confirm DeepSeek's terms allow training on outputs before bulk data is used, D-010)."""

import hashlib
import html
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from training import config


def _page_text(raw: str) -> str:
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.S)
    raw = re.sub(r"</(p|div|li|h\d|br|tr)>|<br\s*/?>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", "", raw))
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    return "\n".join(x.strip() for x in text.split("\n") if x.strip())


def terms_evidence(terms_dir: Path = config.TEACHER_TERMS_DIR) -> dict:
    """What the saved snapshot says, extracted from the saved HTML (never typed in): release/effective dates and
    the verbatim text of Open Platform ToS §4.2 (rights over Inputs and Outputs, incl. (2) assignment of Outputs and
    (3) 'training other models'), plus the snapshot hashes recomputed from the files."""
    meta = json.loads((terms_dir / "terms.json").read_text())
    page = next(p for p in meta["pages"] if "open-platform" in p["url"])
    pages = [
        hashlib.sha256((terms_dir / p["file"]).read_bytes()).hexdigest() for p in meta["pages"]
    ]
    text = _page_text((terms_dir / page["file"]).read_text(encoding="utf8"))
    sec = re.search(r"^4\.2 Subject to.*?(?=^Intellectual Property)", text, flags=re.S | re.M)
    dates = re.search(r"Release date: (.*)\nEffective date: (.*)", text)
    return {
        "snapshot_sha256_recomputed": hashlib.sha256(
            "".join(h + "\n" for h in pages).encode()
        ).hexdigest(),
        "pages": [
            {k: p[k] for k in ("url", "fetched_utc", "http_status", "sha256")}
            for p in meta["pages"]
        ],
        "open_platform_tos_release_date": dates.group(1) if dates else None,
        "open_platform_tos_effective_date": dates.group(2) if dates else None,
        "open_platform_tos_section_4_2": sec.group(0).strip().replace("\n", " ") if sec else None,
        "owner_confirmation": meta["owner_confirmation"],
    }


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
    evidence = None
    if not missing:
        evidence = terms_evidence()
        if evidence["snapshot_sha256_recomputed"] != config.TEACHER_TERMS_SNAPSHOT_SHA256:
            missing.append("terms snapshot files no longer match TEACHER_TERMS_SNAPSHOT_SHA256")
        if not evidence["open_platform_tos_section_4_2"]:
            missing.append("section 4.2 not found in the saved terms")
    card = {
        "status": "INCOMPLETE: " + ", ".join(missing) if missing else "complete",
        "created": datetime.now(UTC).isoformat(),
        "teacher_model": config.DEEPSEEK_MODEL_ID,
        "prompt": config.SYSTEM_PROMPT_V1,
        "prompt_sha256": config.SYSTEM_PROMPT_V1_SHA256,
        "terms_url": config.TEACHER_TERMS_URL,
        "terms_snapshot_sha256": config.TEACHER_TERMS_SNAPSHOT_SHA256,
        "terms_evidence": evidence,
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
