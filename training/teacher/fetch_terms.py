"""Snapshot DeepSeek's terms pages (RULES 5.4, D-010): raw HTML + HTTP status + fetch time + sha256 in terms.json.

uv run python -m training.teacher.fetch_terms --out training/teacher/terms/<date> --confirmation "<owner text>"

curl is called with an argument list (never a shell string, RULES 1) and a generic client name: no account, project
or personal detail is sent. The combined `snapshot_sha256` is the sha256 of the per-page sha256 hex digests, one per
line, in URL order; it is what training/config.py pins as TEACHER_TERMS_SNAPSHOT_SHA256.
"""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

URLS = (
    "https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html",
    "https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html",
)


def curl_argv(url: str, body: Path, headers: Path) -> list[str]:
    return [
        "curl", "--silent", "--show-error", "--location", "--max-time", "60", "--user-agent", "terms-snapshot/1",
        "--dump-header", str(headers), "--output", str(body), "--write-out", "%{http_code}", url,
    ]  # fmt: skip


def snapshot_sha256(pages: list[dict]) -> str:
    return hashlib.sha256("".join(p["sha256"] + "\n" for p in pages).encode()).hexdigest()


def fetch(out: Path, confirmation: str, urls: tuple[str, ...] = URLS) -> dict:
    out.mkdir(parents=True, exist_ok=False)  # never overwrite an earlier snapshot
    pages = []
    for url in urls:
        slug = url.rsplit("/", 1)[-1].removesuffix(".html")
        body, hdr = out / f"{slug}.html", out / f"{slug}.headers.txt"
        when = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = subprocess.run(curl_argv(url, body, hdr), capture_output=True, text=True, check=True)
        pages.append({
            "url": url, "file": body.name, "fetched_utc": when, "http_status": int(r.stdout.strip()),
            "bytes": body.stat().st_size, "sha256": hashlib.sha256(body.read_bytes()).hexdigest(),
        })  # fmt: skip
    meta = {
        "pages": pages, "snapshot_sha256": snapshot_sha256(pages),
        "snapshot_sha256_definition": "sha256 of the per-page sha256 hex digests, one per line, in `pages` order",
        "owner_confirmation": confirmation,
    }  # fmt: skip
    (out / "terms.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--confirmation", required=True)
    a = ap.parse_args()
    m = fetch(a.out, a.confirmation)
    for p in m["pages"]:
        print(p["http_status"], p["bytes"], p["sha256"][:12], p["url"])
    print("snapshot_sha256", m["snapshot_sha256"])


if __name__ == "__main__":
    main()
