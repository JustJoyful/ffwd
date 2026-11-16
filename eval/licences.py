"""Licence audit (RULES §3.5, §7.5): every clip, dataset and model that ships or trains must have a recorded licence.

uv run python -m eval.licences      # exits non-zero listing anything unrecorded
"""

import json
import sys

from training import config

# Third-party assets that go into a release; add a row BEFORE using a new one. Verified against each project's page.
ASSETS = {
    "Qwen/Qwen3-0.6B": "Apache-2.0",
    "Qwen/Qwen3-1.7B": "Apache-2.0",
    "llama.cpp": "MIT",
    "ffmpeg (GPL build)": "GPL-2.0-or-later (project is GPL-3.0, D-016)",
    "deepseek teacher outputs": "DeepSeek terms of use: owner must confirm training on outputs is allowed (D-010)",
}


def audit(manifest: list[dict] | None = None, assets: dict | None = None) -> list[str]:
    problems = []
    manifest = (
        json.loads((config.CORPUS_DIR / "manifest.json").read_text())
        if manifest is None
        else manifest
    )
    for rec in manifest:
        if not (rec.get("licence") or "").strip():
            problems.append(f"clip {rec['id']}: no licence recorded")
        if not (rec.get("source") or "").strip():
            problems.append(f"clip {rec['id']}: no source recorded")
    for name, lic in (ASSETS if assets is None else assets).items():
        if not (lic or "").strip():
            problems.append(f"asset {name}: no licence recorded")
    return problems


def main() -> None:
    problems = audit()
    print("\n".join(problems) or "all recorded")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
