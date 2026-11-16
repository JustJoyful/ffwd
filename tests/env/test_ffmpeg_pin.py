import hashlib
import io
import stat
import tarfile

import pytest

from training import config
from training.env import ffmpeg_pin
from training.env.ffmpeg_version import ffmpeg_version


def fake_ffmpeg(path, version):
    path.write_text(
        f"#!/bin/sh\necho 'ffmpeg version {version} Copyright (c) the FFmpeg developers'\n"
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def test_require_pinned_is_fail_closed_only_when_enforced(tmp_path, monkeypatch):
    ffmpeg_version.cache_clear()
    old = fake_ffmpeg(tmp_path / "old", "9.0.2")
    good = fake_ffmpeg(tmp_path / "good", config.FFMPEG_PIN["version"])
    monkeypatch.setattr(config, "FFMPEG_PIN_ENFORCED", False)
    ffmpeg_pin.require_pinned(old)  # staged: not enforced yet
    monkeypatch.setattr(config, "FFMPEG_PIN_ENFORCED", True)
    with pytest.raises(ffmpeg_pin.PinMismatch, match="9.0.2"):
        ffmpeg_pin.require_pinned(old)
    ffmpeg_pin.require_pinned(good)


def _tarball(path, members):
    with tarfile.open(path, "w:xz") as t:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            t.addfile(info, io.BytesIO(data))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_install_verifies_the_hash_and_extracts_both_tools(tmp_path, monkeypatch):
    d = config.FFMPEG_PIN["dirname"]
    tb = tmp_path / "a.tar.xz"
    sha = _tarball(tb, {f"{d}/ffmpeg": b"x", f"{d}/ffprobe": b"y"})
    monkeypatch.setitem(config.FFMPEG_PIN, "sha256", sha)
    out = ffmpeg_pin.install(tb, home=tmp_path / "home")
    assert (out / "ffmpeg").read_bytes() == b"x" and (out / "ffprobe").exists()
    monkeypatch.setitem(config.FFMPEG_PIN, "sha256", "0" * 64)
    with pytest.raises(ffmpeg_pin.PinMismatch, match="sha256"):
        ffmpeg_pin.install(tb, home=tmp_path / "home2")


def test_install_rejects_path_traversal_members(tmp_path, monkeypatch):
    tb = tmp_path / "evil.tar.xz"
    monkeypatch.setitem(config.FFMPEG_PIN, "sha256", _tarball(tb, {"../escape": b"z"}))
    with pytest.raises(tarfile.TarError):
        ffmpeg_pin.install(tb, home=tmp_path / "home")
    assert not (tmp_path / "escape").exists()
