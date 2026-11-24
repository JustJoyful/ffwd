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


def command(package: Path, repo: str) -> list[str]:
    m = json.loads((package / "ffwd-model.json").read_text())
    tag = f"v{m['version']}"
    gguf = [package / f["path"] for f in m["files"] if f["format"] == "gguf"]
    assets = [*gguf, package / "ffwd-model.json", package / "SHA256SUMS", package / "LICENSE"]
    return [
        "gh", "release", "create", tag, *map(str, assets),
        "--repo", repo, "--title", f"{m['name']} {tag}",
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
    ap.add_argument(
        "--go", action="store_true", help="really create the draft release (default: dry run)"
    )
    a = ap.parse_args(argv)
    problems = verify_package(a.package)
    if problems:
        print("REFUSED: package does not verify: " + "; ".join(problems), file=sys.stderr)
        return 1
    cmd = command(a.package, a.repo)
    print(("RUN: " if a.go else "DRY RUN, would run: ") + " ".join(cmd))
    return subprocess.run(cmd, check=False).returncode if a.go else 0


if __name__ == "__main__":
    sys.exit(main())
