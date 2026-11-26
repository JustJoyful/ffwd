"""Create the GitHub release of a built model package. DRY RUN unless `--go`; never run by the build.

    uv run python scripts/release_github.py --repo OWNER/REPO --package releases/ffwd-0.6b-v1.0.0          # prints the command
    uv run python scripts/release_github.py --repo OWNER/REPO --package releases/ffwd-0.6b-v1.0.0 --go     # runs it

The release is created as a DRAFT: the owner publishes it by hand after looking at it. GitHub release assets are for
people to download; browsers must load the model from the Hugging Face repo (range requests, CORS), not from here.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from training.export.release import verify_package  # noqa: E402


def command(
    package: Path, repo: str, tag: str | None = None, with_weights: bool = False
) -> list[str]:
    m = json.loads((package / "ffwd-model.json").read_text())
    # model-v1.0.0, not v1.0.0: this repo also holds code, and a plain v1.0.0 would clash with a later code release
    tag = tag or f"model-v{m['version']}"
    gguf = [package / f["path"] for f in m["files"] if f["format"] == "gguf"]
    # chat-template.jinja and system-v1.txt are needed to run the model correctly (the prompt is part of the contract)
    assets = [
        *gguf,
        package / "ffwd-model.json",
        package / "SHA256SUMS",
        package / "LICENSE",
        package / "chat-template.jinja",
        package / "system-v1.txt",
    ]
    if with_weights:  # the merged fp16 weights (1.19 GB, under GitHub's 2 GiB per-asset limit)
        assets.append(package / "weights" / "model.safetensors")
    return [
        "gh", "release", "create", tag, *map(str, assets),
        "--repo", repo, "--title", f"{m['name']} v{m['version']}",
        "--notes-file", str(package / "RELEASE_NOTES.md"), "--draft",
    ]  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--repo",
        required=True,
        help="OWNER/REPO that gets the release (no default: see releases/README.md)",
    )
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--tag", help="release tag (default: model-v<version>)")
    ap.add_argument(
        "--with-weights",
        action="store_true",
        help="also attach weights/model.safetensors (1.19 GB)",
    )
    ap.add_argument(
        "--go", action="store_true", help="really create the draft release (default: dry run)"
    )
    a = ap.parse_args(argv)
    problems = verify_package(a.package)
    if problems:
        print("REFUSED: package does not verify: " + "; ".join(problems), file=sys.stderr)
        return 1
    cmd = command(a.package, a.repo, a.tag, a.with_weights)
    print(("RUN: " if a.go else "DRY RUN, would run: ") + " ".join(cmd))
    return subprocess.run(cmd, check=False).returncode if a.go else 0


if __name__ == "__main__":
    sys.exit(main())
