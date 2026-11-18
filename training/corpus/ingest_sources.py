"""Ingest the owner's source videos into the corpus: cuts, whole-file copies and derived clips (Phase 1).

uv run python -m training.corpus.ingest_sources [--only ID ...] [--rebuild-check]

Reads `sources.json` (one declarative row per clip). For each row not yet in the manifest it builds the media
(`-c copy` cut, byte copy, or a derived-clip command on a parent clip), probes the result, asserts the properties
the label claims (`must`), and only then registers it through `add_clip`. A clip whose assertions fail is never
written (RULES §4.1: never fake a property). The manifest record carries the exact command (placeholders
{videos}/{corpus}/{out}), source sha256, cut start, ffmpeg version and the real probed duration, so every clip can
be rebuilt from the manifest alone. Sources live in videos/ (untracked); only the manifest and this table are.
Argument lists only, never a shell string (RULES §1).
"""

import argparse
import functools
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from training import config
from training.corpus.add_clip import add_clip
from training.env.ffmpeg_pin import ffmpeg_bin, ffprobe_bin
from training.env.ffmpeg_version import ffmpeg_version
from training.env.probe import display_size, first_packet_pts, probe

SOURCES = Path(__file__).with_name("sources.json")
VIDEOS_DIR = config.REPO_ROOT / "videos"
ORIGINS = ("downloaded", "own-recording", "derived")
MAX_AV_SKEW_MS = 25.0  # one AAC frame of priming (21.3 ms) is what the synthetic corpus already carries; the checker's
# +-40 ms offset window (OFFSET_TOLERANCE_MS) is absolute, so more inherent skew would fail correct F11 solutions
_QUIET = ["-nostdin", "-v", "error", "-y"]


@functools.cache
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def raw_streams(path: Path) -> list[dict]:
    out = subprocess.run(
        [ffprobe_bin(), "-v", "error", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return json.loads(out.stdout)["streams"]


def measured_fps(path: Path) -> float:
    """Frame rate from packet timestamps: container headers can lie (the BBB webm says avg=30 but is 60 fps)."""
    out = subprocess.run(
        [ffprobe_bin(), "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    ts = sorted({float(x) for x in out.stdout.split() if re.fullmatch(r"-?[\d.]+", x)})
    return (len(ts) - 1) / (ts[-1] - ts[0])


def _mean_db(path: Path) -> float:
    err = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    ).stderr  # fmt: skip
    return float(re.search(r"mean_volume: (-?[\d.]+) dB", err).group(1))  # type: ignore[union-attr]


def av_offset_ms(path: Path) -> float | None:
    """Audio minus video first-packet pts in ms, the checker's own measure (container start_time hides edit lists)."""
    v0, a0 = first_packet_pts(path, "video"), first_packet_pts(path, "audio")
    return None if v0 is None or a0 is None else (a0 - v0) * 1000


def check_must(
    path: Path, pr: dict, raw: list[dict], must: dict, siblings: dict, parent: Path | None
) -> list[str]:
    """Problems found when the probed clip is compared with what its label claims (empty = all true)."""
    bad: list[str] = []
    v = next((s for s in pr["streams"] if s["type"] == "video"), None)
    audio = [s for s in pr["streams"] if s["type"] == "audio"]
    w, h = display_size(v) if v else (0, 0)

    def need(ok: bool, msg: str) -> None:
        if not ok:
            bad.append(msg)

    if "video_codec" in must:
        need(
            v is not None and v["codec"] == must["video_codec"],
            f"video_codec {v and v['codec']} != {must['video_codec']}",
        )
    if "audio_codec" in must:
        need(
            bool(audio) and audio[0]["codec"] == must["audio_codec"],
            f"audio_codec != {must['audio_codec']}",
        )
    if "audio" in must:
        need(bool(audio) == must["audio"], f"audio present={bool(audio)}, expected {must['audio']}")
    if "audio_streams" in must:
        need(
            len(audio) == must["audio_streams"],
            f"audio_streams {len(audio)} != {must['audio_streams']}",
        )
    if "min_width" in must:
        need(w >= must["min_width"], f"min_width {w} < {must['min_width']}")
    if "aspect" in must:
        lo, hi = must["aspect"]
        need(
            h > 0 and lo <= w / h <= hi,
            f"aspect {w}x{h}={w / h if h else 0:.3f} outside [{lo}, {hi}]",
        )
    if "container" in must:
        need(
            must["container"] in pr["container"],
            f"container {pr['container']} lacks {must['container']}",
        )
    if "fps" in must:
        lo, hi = must["fps"]
        need(v is not None and lo <= v["fps"] <= hi, f"fps {v and v['fps']} outside [{lo}, {hi}]")
    if "fps_measured" in must:
        lo, hi = must["fps_measured"]
        f = measured_fps(path)
        need(lo <= f <= hi, f"measured fps {f:.2f} outside [{lo}, {hi}]")
    if must.get("rotation_nonzero"):
        need(bool(v and v.get("rotation")), "no rotation side data")
    if must.get("portrait_display"):
        need(h > w, f"display {w}x{h} is not portrait")
    if "profile" in must:
        prof = next((s.get("profile") for s in raw if s["codec_type"] == "video"), None)
        need(prof == must["profile"], f"profile {prof} != {must['profile']}")
    if "audio_title_1" in must:
        titles = [s.get("tags", {}).get("title") for s in raw if s["codec_type"] == "audio"]
        need(len(titles) > 1 and titles[1] == must["audio_title_1"], f"audio titles {titles}")
    for key, ids in (("same_as", True), ("differs_res_from", False)):
        for other in must.get(key, []):
            o = next((s for s in siblings[other]["streams"] if s["type"] == "video"), None)
            same = (
                o is not None
                and v is not None
                and all(o[k] == v[k] for k in ("codec", "width", "height", "fps"))
            )
            if ids:
                need(same, f"codec/res/fps differ from {other}")
            else:
                need(
                    o is not None
                    and v is not None
                    and (o["width"], o["height"]) != (v["width"], v["height"]),
                    f"same resolution as {other}",
                )
    if "offset_ms" in must:
        lo, hi = must["offset_ms"]
        off = av_offset_ms(path)
        need(
            off is not None and lo <= off <= hi, f"audio-video offset {off} ms outside [{lo}, {hi}]"
        )
    if "gain_db_vs_parent" in must and parent is not None:
        lo, hi = must["gain_db_vs_parent"]
        g = _mean_db(path) - _mean_db(parent)
        need(lo <= g <= hi, f"gain {g:.1f} dB outside [{lo}, {hi}]")
    return bad


def _command(row: dict, corpus_dir: Path, records: dict) -> list[str] | None:
    """Recorded ffmpeg argument list with {videos}/{corpus}/{out} placeholders (None = whole-file copy)."""
    if row["origin"] == "derived":
        parent = "{corpus}/" + records[row["parent"]]["file"]
        return [*_QUIET, *[t.replace("{parent}", parent) for t in row["ffmpeg"]]]
    if row["cut"] is None:
        return None
    c = row["cut"]
    return [
        *_QUIET, "-ss", str(c["start"]), "-i", "{videos}/" + row["src"], "-t", str(c["duration"]),
        "-map", "0:v:0", "-map", "0:a?", "-c", "copy", "-avoid_negative_ts", "make_zero", "{out}",
    ]  # fmt: skip


def _run(command: list[str], videos: Path, corpus: Path, out: Path) -> None:
    argv = [
        t.replace("{videos}", str(videos))
        .replace("{corpus}", str(corpus))
        .replace("{out}", str(out))
        for t in command
    ]
    subprocess.run([ffmpeg_bin(), *argv], check=True, capture_output=True)


def _ext(row: dict) -> str:
    return row["ext"] if row["origin"] == "derived" else Path(row["src"]).suffix.lower()


def build_clip(row: dict, videos: Path, corpus: Path, work: Path) -> dict | None:
    """Build, verify and register one row. Returns the manifest record, or None when the id already exists."""
    records = {r["id"]: r for r in json.loads((corpus / "manifest.json").read_text())}
    if row["id"] in records:
        return None
    command = _command(row, corpus, records)
    src = videos / row["src"] if row.get("src") else None
    out = work / f"{row['id']}{_ext(row)}"
    if command is None:
        out = src  # type: ignore[assignment]
    else:
        _run(command, videos, corpus, out)
    parent = corpus / records[row["parent"]]["file"] if row.get("parent") else None
    offset = av_offset_ms(out)
    problems = check_must(
        out, probe(out), raw_streams(out), row.get("must", {}),
        {k: v["probe"] for k, v in records.items()}, parent,
    )  # fmt: skip
    if (
        offset is not None
        and abs(offset) > MAX_AV_SKEW_MS
        and not ("av_skew" in row["tags"] or "offset_ms" in row.get("must", {}))
    ):
        problems.append(
            f"audio-video offset {offset:.1f} ms exceeds {MAX_AV_SKEW_MS} ms: declare it with the av_skew tag"
        )
    if problems:
        if command is not None:
            out.unlink(missing_ok=True)
        raise ValueError(f"{row['id']}: label claims not true: " + "; ".join(problems))
    provenance = {
        "source_file": row.get("src"), "source_sha256": sha256_file(src) if src else None,
        "archive": row.get("archive"), "cut_start_s": (row.get("cut") or {}).get("start"),
        "cut_duration_s": (row.get("cut") or {}).get("duration"), "command": command,
        "ffmpeg_version": ffmpeg_version() if command else None,
    }  # fmt: skip
    extra = {
        "origin": row["origin"], "synthetic": row["synthetic"], "restricted": row["restricted"],
        "attribution": row["attribution"], "consent": row.get("consent"), "parent": row.get("parent"),
        "source_url": row.get("source_url"), "measured_offset_ms": None if offset is None else round(offset, 1),
        "provenance": provenance, "gold": row.get("gold"),
    }  # fmt: skip
    rec = add_clip(
        out, row["id"], row["licence"], row.get("source_url") or row["origin"], row["role"], corpus,
        tags=tuple(row["tags"]), known_offset_ms=row.get("known_offset_ms"), extra=extra,
    )  # fmt: skip
    if command is not None:
        out.unlink(missing_ok=True)
    return rec


def _rebuild(rec: dict, videos: Path, corpus: Path, work: Path) -> Path:
    out = work / rec["file"]
    _run(rec["provenance"]["command"], videos, corpus, out)
    return out


def rebuild_sha(rec: dict, videos: Path, corpus: Path, work: Path) -> str:
    """Re-run a clip's recorded command from the manifest record alone; return the new file's sha256."""
    cmd = rec["provenance"]["command"]
    if cmd is None:
        return sha256_file(videos / rec["provenance"]["source_file"])
    out = _rebuild(rec, videos, corpus, work)
    try:
        return hashlib.sha256(out.read_bytes()).hexdigest()
    finally:
        out.unlink(missing_ok=True)


def content_md5(path: Path) -> str:
    """Hash of the stream-copied packets: equal when only muxer-generated ids (webm/mkv UIDs) differ."""
    r = subprocess.run(
        [ffmpeg_bin(), "-nostdin", "-v", "error", "-i", str(path), "-map", "0", "-c", "copy", "-f", "md5", "-"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return r.stdout.strip()


def rebuild_verdict(rec: dict, videos: Path, corpus: Path, work: Path) -> str:
    """identical (same bytes) | same-content (packets equal, container ids differ) | DIFFERENT."""
    if rec["provenance"]["command"] is None:
        return (
            "identical" if rebuild_sha(rec, videos, corpus, work) == rec["sha256"] else "DIFFERENT"
        )
    out = _rebuild(rec, videos, corpus, work)
    try:
        if hashlib.sha256(out.read_bytes()).hexdigest() == rec["sha256"]:
            return "identical"
        return (
            "same-content" if content_md5(out) == content_md5(corpus / rec["file"]) else "DIFFERENT"
        )
    finally:
        out.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None, help="build only these clip ids")
    ap.add_argument(
        "--rebuild-check", action="store_true", help="re-run recorded commands and compare sha256"
    )
    ap.add_argument("--videos", type=Path, default=VIDEOS_DIR)
    a = ap.parse_args()
    work = a.videos / "_work"
    work.mkdir(exist_ok=True)
    if a.rebuild_check:
        for r in json.loads((config.CORPUS_DIR / "manifest.json").read_text()):
            if "provenance" in r:
                print(f"{r['id']:<16} {rebuild_verdict(r, a.videos, config.CORPUS_DIR, work)}")
        return
    for row in json.loads(SOURCES.read_text()):
        if a.only and row["id"] not in a.only:
            continue
        rec = build_clip(row, a.videos, config.CORPUS_DIR, work)
        if rec is None:
            print(f"{row['id']:<16} already in manifest, skipped")
            continue
        p = rec["probe"]
        print(
            f"{rec['id']:<16} {rec['role']:<9} {p['duration_s']:>7.2f}s {p['size_bytes'] / 1e6:>7.1f}MB tags={rec['tags']}"
        )
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
