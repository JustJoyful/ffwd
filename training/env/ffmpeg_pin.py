"""The pinned FFmpeg (D-024, D-029): install it, and refuse to run the checker or executor on anything else.

uv run python -m training.env.ffmpeg_pin install [--tarball <already downloaded file>]   # verify sha256, extract
uv run python -m training.env.ffmpeg_pin check                                          # print the version in use
"""

import argparse
import hashlib
import tarfile
import urllib.request
from pathlib import Path

from training import config
from training.env.ffmpeg_version import ffmpeg_version


class PinMismatch(RuntimeError):
    pass


def require_pinned(binary: str | None = None) -> None:
    """Fail closed (when enforced) unless `binary` reports exactly the pinned FFmpeg version."""
    if not config.FFMPEG_PIN_ENFORCED:
        return
    got = ffmpeg_version(binary or config.FFMPEG_BIN)
    if got != config.FFMPEG_PIN["version"]:
        raise PinMismatch(
            f"FFmpeg {got} found, pinned build is {config.FFMPEG_PIN['version']} (D-024): "
            "run `uv run python -m training.env.ffmpeg_pin install`"
        )


def ffmpeg_bin() -> str:
    require_pinned()
    return config.FFMPEG_BIN


def ffprobe_bin() -> str:
    require_pinned()
    return config.FFPROBE_BIN


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def install(tarball: Path | None = None, home: Path = config.FFMPEG_PIN_HOME) -> Path:
    """Verify the tarball against the pinned sha256 (downloading it if not given), extract it under `home`.
    Returns the directory holding `ffmpeg` and `ffprobe`. Never runs the binaries."""
    home.mkdir(parents=True, exist_ok=True)
    if tarball is None:
        tarball = home / "download.tar.xz"
        if not tarball.exists():
            urllib.request.urlretrieve(
                config.FFMPEG_PIN["url"], tarball
            )  # noqa: S310 (pinned https URL)
    got = _sha256(tarball)
    if got != config.FFMPEG_PIN["sha256"]:
        raise PinMismatch(
            f"sha256 mismatch for {tarball}: {got} != pinned {config.FFMPEG_PIN['sha256']}"
        )
    with tarfile.open(tarball) as t:
        t.extractall(
            home, filter="data"
        )  # "data": rejects absolute paths, traversal and special files
    bin_dir = home / config.FFMPEG_PIN["dirname"]
    for tool in ("ffmpeg", "ffprobe"):
        if not (bin_dir / tool).exists():
            raise PinMismatch(f"{tool} missing from the extracted archive at {bin_dir}")
    return bin_dir


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("install")
    i.add_argument("--tarball", type=Path)
    sub.add_parser("check")
    a = ap.parse_args()
    if a.cmd == "install":
        print(install(a.tarball))
    else:
        print(ffmpeg_version(config.FFMPEG_BIN), "(pinned:", config.FFMPEG_PIN["version"] + ")")


if __name__ == "__main__":
    main()
