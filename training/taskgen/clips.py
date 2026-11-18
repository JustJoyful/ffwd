"""Clip index for the task generator: probe facts + tags per corpus clip, and named pools of clips that suit a chore."""

import json
from dataclasses import dataclass
from pathlib import Path

from training import config
from training.env.checker import _integrated_loudness
from training.env.probe import display_size


@dataclass(frozen=True)
class Clip:
    id: str
    duration_s: float
    width: int  # display size (rotation applied)
    height: int
    fps: float | None
    vcodec: str | None
    container: str
    has_audio: bool
    size_bytes: int
    tags: tuple[str, ...]
    known_offset_ms: float | None
    path: Path


class ClipIndex:
    def __init__(self, manifest: Path = config.CORPUS_DIR / "manifest.json"):
        self.clips: dict[str, Clip] = {}
        self._lufs: dict[str, float | None] = {}
        for r in json.loads(manifest.read_text()):
            if r.get("role", config.CLIP_ROLE_DEFAULT) == "test-real":
                continue  # D-027(b): never an input of generated tasks
            if r.get("restricted"):
                continue  # licence unverified: no generated task, in any split, until the owner confirms
            p = r["probe"]
            v = next((s for s in p["streams"] if s["type"] == "video"), None)
            w, h = display_size(v) if v else (0, 0)
            self.clips[r["id"]] = Clip(
                id=r["id"],
                duration_s=p["duration_s"],
                width=w,
                height=h,
                fps=v["fps"] if v else None,
                vcodec=v["codec"] if v else None,
                container=p["container"].split(",")[0],
                has_audio=any(s["type"] == "audio" for s in p["streams"]),
                size_bytes=p["size_bytes"],
                tags=tuple(r.get("tags", [])),
                known_offset_ms=r.get("known_offset_ms"),
                path=manifest.parent / r["file"],
            )

    def loudness(self, clip_id: str) -> float | None:
        """Integrated loudness (LUFS) of a clip, measured once (F10 gold targets derive from it)."""
        if clip_id not in self._lufs:
            self._lufs[clip_id] = _integrated_loudness(self.clips[clip_id].path)
        return self._lufs[clip_id]

    def __getitem__(self, clip_id: str) -> Clip:
        return self.clips[clip_id]

    def pool(self, *, audio: bool | None = None, min_s: float = 0, max_s: float = 1e9,
             vcodec: str | None = None, exclude_tags: tuple[str, ...] = (),
             only_tags: tuple[str, ...] = ()) -> list[Clip]:  # fmt: skip
        out = []
        for c in self.clips.values():
            if c.vcodec is None or not (min_s <= c.duration_s <= max_s):
                continue
            if audio is not None and c.has_audio != audio:
                continue
            if vcodec and c.vcodec != vcodec:
                continue
            if set(c.tags) & set(exclude_tags) or (only_tags and not set(c.tags) & set(only_tags)):
                continue
            out.append(c)
        return sorted(out, key=lambda c: c.id)  # sorted: seeded sampling is reproducible
