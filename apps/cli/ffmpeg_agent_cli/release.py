"""Read and verify a model release package (D-053). Fail closed: any doubt raises ReleaseRefused and nothing starts.

The file checks are `training.export.release.file_problem`, the same ones `release verify` runs; this module only adds
the version rules and a verified-marker so the 444 MB GGUF is hashed once, not on every run.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from apps.cli.ffmpeg_agent_cli import __version__
from training import config
from training.env.chat_template import render
from training.export.hub import sha256_file
from training.export.release import file_problem
from training.protocol import validate

MANIFEST = "ffwd-model.json"


class ReleaseRefused(Exception):
    pass


@dataclass(frozen=True)
class Release:
    root: Path
    manifest: dict
    gguf: Path  # the file with role "shipped"
    template: Path
    system_prompt: str

    @property
    def runtime(self) -> dict:
        return self.manifest["runtime"]


def _semver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def _marker_file() -> Path:
    return (
        Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "ffwd" / "verified.json"
    )


def _cached_sha(path: Path, expected: str) -> str:
    """sha256 of `path`, skipped when a marker says this path+size+mtime already hashed to `expected`.
    The marker is written only after a full hash pass that matched, in the user cache (never inside the package:
    `release verify` would flag an unlisted file). shortcut: an edit that keeps size and mtime is not noticed.
    """
    st, mark = path.stat(), _marker_file()
    key = f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}"
    try:
        marks = json.loads(mark.read_text())
    except (OSError, ValueError):
        marks = {}
    if not isinstance(marks, dict):
        marks = {}
    if marks.get(key) == expected:
        return expected
    got = sha256_file(path)
    if got == expected:
        try:
            mark.parent.mkdir(parents=True, exist_ok=True)
            mark.write_text(json.dumps({**marks, key: got}))
        except OSError:
            pass  # no cache folder: the next run just hashes again
    return got


def load_release(root: Path) -> Release:
    try:
        m = json.loads((root / MANIFEST).read_text())
    except (OSError, ValueError) as e:
        raise ReleaseRefused(f"cannot read {root / MANIFEST}: {e}") from None
    if errors := validate("model", m):
        raise ReleaseRefused(f"{MANIFEST} does not match the schema: {errors[0]}")
    # Exact match: ARCHITECTURE §12 says protocol_version mismatches "fail loudly"; no looser rule exists.
    if m["protocol_version"] != config.PROTOCOL_VERSION:
        raise ReleaseRefused(
            f"model protocol_version {m['protocol_version']} != {config.PROTOCOL_VERSION} this CLI speaks"
        )
    if _semver(m["min_app_version"]) > _semver(__version__):
        raise ReleaseRefused(
            f"model needs app version {m['min_app_version']}, this CLI is {__version__}"
        )
    shipped = [f for f in m["files"] if f["role"] == "shipped" and f["format"] == "gguf"]
    if len(shipped) != 1:
        raise ReleaseRefused("the manifest must list exactly one shipped gguf")
    by_path = {f["path"]: f for f in m["files"]}
    entries = [shipped[0]]
    for key in (
        "prompt",
        "chat_template",
    ):  # the block's hash and the files[] hash must be the same file
        e = by_path.get(m[key]["file"])
        if e is None or e["sha256"] != m[key]["sha256"]:
            raise ReleaseRefused(f"{key} is not listed in files with the same sha256")
        entries.append(e)
    for e in entries:
        sha = (lambda p, e=e: _cached_sha(p, e["sha256"])) if e["format"] == "gguf" else sha256_file
        if problem := file_problem(root, e, sha):
            raise ReleaseRefused(problem)
    return Release(
        root,
        m,
        root / shipped[0]["path"],
        root / m["chat_template"]["file"],
        (root / m["prompt"]["file"]).read_text(),
    )


def run_canary(rel: Release, server) -> tuple[bool, str]:
    """The manifest's canary against a started server: greedy 20 tokens, the first `min_matched` must equal the
    expected ids (the same prefix rule as the website). Unverified against a real llama-server: no binary here.
    """
    c = rel.manifest["canary"]
    if c["file_sha256"] != next(
        f["sha256"] for f in rel.manifest["files"] if f["path"] == rel.gguf.name
    ):
        return False, "the canary was made with a different file than the shipped one"
    msgs = [
        {"role": "system", "content": rel.system_prompt},
        {"role": "user", "content": c["user_turn"]},
    ]
    prompt = render(msgs, add_generation_prompt=True)
    if hashlib.sha256(prompt.encode()).hexdigest() != c["rendered_prompt_sha256"]:
        return False, "the rendered canary prompt differs from the manifest"
    body = {"prompt": prompt, "n_predict": c["n_predict"], "temperature": 0, "cache_prompt": False}
    got = server.post("/completion", body | {"return_tokens": True}).get("tokens", [])
    want = c["expected_token_ids"]
    n = next(
        (i for i, (a, b) in enumerate(zip(got, want, strict=False)) if a != b),
        min(len(got), len(want)),
    )
    return n >= c["match"]["min_matched"], f"{n} of {c['match']['of']} tokens match"
