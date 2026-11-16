"""F1-F12 samplers: each returns a `Draft` (gold spec patch + reference plan + phrasing slots) or None.

Parameters are drawn from clip probes so tasks are feasible; `verify_draft` (verify.py) still executes every
reference solution against the checker, so an infeasible draft is dropped rather than emitted.
"""

import random
from collections.abc import Callable

from training.env.checker import expected_frame_range
from training.taskgen.clips import Clip, ClipIndex
from training.taskgen.frag import Draft

TOL = 0.15  # trim tolerance used throughout (same as the hand-written spike tasks)
SAMPLERS: dict[str, Callable[..., Draft | None]] = {}


def family(fid: str):
    def reg(fn):
        SAMPLERS[fid] = fn
        return fn

    return reg


def _h264(ci: ClipIndex, **kw) -> list[Clip]:
    return ci.pool(
        vcodec="h264",
        exclude_tags=("vfr", "rotation", "webm", "prores", "portrait", "av_offset"),
        **kw,
    )


def _pick(rng: random.Random, ci: ClipIndex, clip: str | None, pool: list[Clip]) -> Clip:
    """A forced clip (compositions share one input) bypasses the pool; verify_draft still checks feasibility."""
    return ci[clip] if clip else rng.choice(pool)


def _even(x: float) -> int:
    return max(2, round(x / 2) * 2)


def _n(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def _mmss(s: int) -> str:
    return f"{s // 60}:{s % 60:02d}"


def _times(draft: Draft, start, end) -> dict:
    return {"time": {"start_s": start, "end_s": end, "tolerance_s": TOL}}


@family("F1")
def f1(rng: random.Random, ci: ClipIndex, clip: str | None = None) -> Draft | None:
    c = _pick(rng, ci, clip, _h264(ci, audio=True, min_s=4))
    D = c.duration_s
    kind = rng.choice(["cut_first", "keep_range", "last_n", "first_n"])
    d = Draft(["F1"], [c.id], [f"f1.{kind}"], copy_mode="stream")
    if kind == "cut_first":
        n = rng.randint(1, max(1, int(D // 2)))
        d.trim, d.spec, d.slots = (n, None), _times(d, n, None), {"n": _n(n)}
    elif kind == "last_n":
        n = rng.randint(1, max(1, int(D // 2)))
        d.trim, d.spec, d.slots = (D - n, None), _times(d, D - n, None), {"n": _n(n)}
    elif kind == "first_n":
        n = rng.randint(1, max(1, int(D // 2)))
        d.trim, d.spec, d.slots = (0, n), _times(d, 0, n), {"n": _n(n)}
    else:
        s = rng.randint(0, max(0, int(D) - 4))
        e = rng.randint(s + 2, min(int(D), s + max(2, int(D) // 2)))
        d.trim, d.spec = (s, e), _times(d, s, e)
        d.slots = {"s": _n(s), "e": _n(e), "s_mmss": _mmss(s), "e_mmss": _mmss(e)}
    return d


@family("F2")
def f2(rng: random.Random, ci: ClipIndex, clip: str | None = None) -> Draft | None:
    pool = [
        c
        for c in ci.pool(audio=True, vcodec="h264")
        if (c.width, c.height) == (1280, 720)
        and c.fps == 30
        and "vfr" not in c.tags
        and "mono" not in c.tags
        and "av_offset" not in c.tags
        and c.container == "mov"
    ]
    n = rng.choice([2, 2, 3])
    clips = rng.sample(pool, n)
    total = sum(c.duration_s for c in clips)
    d = Draft(["F2"], [c.id for c in clips], ["f2.merge"], merge=True)
    d.spec = {"time": {"start_s": None, "end_s": total, "tolerance_s": 0.2}}
    d.slots = {"count": {2: "two", 3: "three"}[n], "count_n": str(n)}
    if rng.random() < 0.35:
        d.spec |= {"video": {"width": 1280, "height": 720}}
        d.intents = ["f2.merge_same_size"]
    return d


@family("F3")
def f3(rng: random.Random, ci: ClipIndex, clip: str | None = None) -> Draft | None:
    kinds = {
        "hevc": "f3.iphone",
        "vp9": "f3.webm",
        "mpeg4": "f3.avi",
        "prores": "f3.prores",
        "h264": "f3.mkv",
    }
    pool = [
        c
        for c in ci.pool(audio=True)
        if c.vcodec in kinds and (c.vcodec != "h264" or c.container == "matroska")
    ]
    c = _pick(rng, ci, clip, pool)
    if c.vcodec not in kinds or (c.vcodec == "h264" and c.container != "matroska"):
        return None  # forced clips that are already compatible have nothing to convert
    d = Draft(["F3"], [c.id], [kinds[c.vcodec]])
    d.spec = {"video": {"codec": "h264", "pix_fmt": "yuv420p"}, "audio": {"codec": "aac"}}
    d.copy_mode = "stream" if c.vcodec == "h264" else "auto"  # mkv h264/aac remuxes losslessly
    d.slots = {
        "fmt": {"hevc": "HEVC", "vp9": "WebM", "mpeg4": "AVI", "prores": "ProRes", "h264": "MKV"}[
            c.vcodec
        ]
    }
    return d


@family("F4")
def f4(rng: random.Random, ci: ClipIndex, clip: str | None = None) -> Draft | None:
    c = _pick(rng, ci, clip, _h264(ci, min_s=2))
    kind = rng.choice(["height", "width", "vertical", "square"])
    d = Draft(["F4"], [c.id], [f"f4.{kind}"])
    if kind == "height":
        h = rng.choice([480, 720, 360])
        if h >= c.height:
            return None
        w = _even(c.width * h / c.height)
        d.vf, d.spec, d.slots = (
            [("scale", f"scale=-2:{h}")],
            {"video": {"width": w, "height": h}},
            {"h": str(h)},
        )
    elif kind == "width":
        w = rng.choice([640, 480, 320])
        if w >= c.width:
            return None
        h = _even(c.height * w / c.width)
        d.vf, d.spec, d.slots = (
            [("scale", f"scale={w}:-2")],
            {"video": {"width": w, "height": h}},
            {"w": str(w)},
        )
    else:
        w, h = (1080, 1920) if kind == "vertical" else (1080, 1080)
        d.vf = [("scale", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}")]
        d.spec, d.slots = {"video": {"width": w, "height": h}}, {"w": str(w), "h": str(h)}
    return d


@family("F5")
def f5(rng: random.Random, ci: ClipIndex, clip: str | None = None) -> Draft | None:
    c = _pick(rng, ci, clip, _h264(ci, min_s=2))
    deg = rng.choice([90, 270, 180])
    lossless = rng.random() < 0.5
    name = {90: "cw", 270: "ccw", 180: "flip"}[deg]
    d = Draft(["F5"], [c.id], [f"f5.{name}{'_lossless' if lossless else ''}"])
    w, h = (c.height, c.width) if deg in (90, 270) else (c.width, c.height)
    d.spec = {"video": {"rotation": deg, "width": w, "height": h}}
    if lossless:
        d.copy_mode, d.rotation_cw = "display_rotation", deg
        d.spec["lossless"] = True
    else:
        chain = {90: "transpose=1", 270: "transpose=2", 180: "hflip,vflip"}[deg]
        d.vf = [("rotate", chain)]
    d.slots = {"deg": "90" if deg != 180 else "180"}
    return d


@family("F6")
def f6(rng: random.Random, ci: ClipIndex, clip: str | None = None) -> Draft | None:
    c = _pick(rng, ci, clip, _h264(ci, audio=True, min_s=4))
    target = rng.choice([1, 2, 3, 5]) * 1_000_000
    if target > 0.5 * c.size_bytes:
        return None
    kbps = int((target * 8 * 0.85) / c.duration_s / 1000) - 64
    if kbps < 150:
        return None
    d = Draft(["F6"], [c.id], ["f6.size"], bitrate_kbps=kbps)
    d.spec = {"size_max_bytes": target}
    d.slots = {"mb": str(target // 1_000_000)}
    if rng.random() < 0.3:
        d.spec |= {"video": {"height": c.height}}
        d.intents, d.slots["res"] = ["f6.size_keep_res"], f"{c.height}p"
    return d


@family("F7")
def f7(rng: random.Random, ci: ClipIndex, clip: str | None = None) -> Draft | None:
    c = _pick(rng, ci, clip, _h264(ci, min_s=4))
    fmt = rng.choice(["png", "jpg"])
    if rng.random() < 0.2:
        d = Draft(
            ["F7"],
            [c.id],
            ["f7.first_frame"],
            kind="image_sequence",
            container=None,
            frames_fmt=fmt,
        )
        d.spec = {"frames": {"interval_s": None, "expected_count": 1, "format": fmt}}
        d.slots = {"fmt": fmt.upper() if fmt == "jpg" else "PNG"}
        return d
    iv = rng.choice([1, 2, 5])
    lo, hi = expected_frame_range(c.duration_s, iv, c.fps)
    if (
        lo != hi or hi < 2
    ):  # boundary cases are legitimately ambiguous: keep them out of the gold tasks
        return None
    d = Draft(
        ["F7"],
        [c.id],
        ["f7.interval"],
        kind="image_sequence",
        container=None,
        frames_interval=iv,
        frames_fmt=fmt,
    )
    d.spec = {"frames": {"interval_s": iv, "expected_count": hi, "format": fmt}}
    d.slots = {"iv": _n(iv), "fmt": "JPG" if fmt == "jpg" else "PNG"}
    return d


@family("F8")
def f8(rng: random.Random, ci: ClipIndex, clip: str | None = None) -> Draft | None:
    c = _pick(rng, ci, clip, _h264(ci, min_s=3))
    w = rng.choice([240, 320, 480])
    d = Draft(["F8"], [c.id], ["f8.whole"], kind="gif", container="gif", gif_width=w)
    d.spec = {"video": {"width": w}}
    d.slots = {"w": str(w)}
    if rng.random() < 0.5 and c.duration_s >= 6:
        s = rng.randint(0, int(c.duration_s) - 4)
        e = s + rng.randint(2, 4)
        d.trim, d.spec["time"] = (s, e), {"start_s": s, "end_s": e, "tolerance_s": 0.2}
        d.intents, d.slots = ["f8.range"], d.slots | {
            "s": str(s),
            "e": str(e),
            "s_mmss": _mmss(s),
            "e_mmss": _mmss(e),
        }
    elif c.duration_s > 6:
        return None  # a whole-clip GIF of a long clip is absurd
    return d


@family("F9")
def f9(rng: random.Random, ci: ClipIndex, clip: str | None = None) -> Draft | None:
    c = _pick(rng, ci, clip, _h264(ci, audio=True, min_s=2))
    if rng.random() < 0.5:
        d = Draft(["F9"], [c.id], ["f9.mp3"], kind="audio", container="mp3")
        d.spec = {"audio": {"codec": "mp3"}}
    else:
        d = Draft(["F9"], [c.id], ["f9.remove"], drop_audio=True, copy_mode="stream")
        d.spec = {"audio": {"present": False}}
    return d


@family("F10")
def f10(rng: random.Random, ci: ClipIndex, clip: str | None = None) -> Draft | None:
    c = _pick(rng, ci, clip, _h264(ci, audio=True, min_s=2))
    lufs = ci.loudness(c.id)
    if lufs is None:
        return None
    if rng.random() < 0.5:
        t = rng.choice([-23, -16, -14])
        d = Draft(["F10"], [c.id], ["f10.normalize"], af=[f"loudnorm=I={t}"], copy_mode="stream")
        d.spec, d.slots = {"audio": {"loudness_lufs": t}}, {"lufs": str(t)}
    else:
        db = rng.choice([6, 10, 20])
        if (
            lufs + db > -14
        ):  # a boost into clipping no longer lands on lufs+db: not a well-defined task
            return None
        d = Draft(["F10"], [c.id], ["f10.boost"], af=[f"volume={db}dB"], copy_mode="stream")
        d.spec, d.slots = {"audio": {"loudness_lufs": round(lufs + db, 1)}}, {"db": str(db)}
    return d


@family("F11")
def f11(rng: random.Random, ci: ClipIndex, clip: str | None = None) -> Draft | None:
    baked = ci.pool(audio=True, only_tags=("av_offset",))
    plain = [
        c
        for c in _h264(ci, audio=True, min_s=2)
        if c.known_offset_ms is None and c.container == "mov"
    ]
    if rng.random() < 0.4:
        c = rng.choice(baked)
        late = c.known_offset_ms > 0  # audio starts after the video
        d = Draft(["F11"], [c.id], ["f11.fix_late" if late else "f11.fix_early"])
        d.offset_shift_ms, d.spec = -c.known_offset_ms, {"audio": {"offset_ms": 0}}
        d.slots = {"sec": "half a second", "ms": "500"}
        return d
    c = rng.choice(plain)
    ms = rng.choice([100, 200, 300, 500])
    delay = rng.random() < 0.5
    d = Draft(["F11"], [c.id], ["f11.delay" if delay else "f11.advance"])
    d.offset_shift_ms = ms if delay else -ms
    d.spec = {"audio": {"offset_ms": ms if delay else -ms}}
    d.slots = {"ms": str(ms), "sec": _n(ms / 1000)}
    return d


@family("F12")
def f12(rng: random.Random, ci: ClipIndex, clip: str | None = None) -> Draft | None:
    c = _pick(rng, ci, clip, _h264(ci, min_s=4))
    if rng.random() < 0.6:
        f = rng.choice([2, 0.5, 1.5])
        d = Draft(["F12"], [c.id], ["f12.speed_up" if f > 1 else "f12.slow_down"], speed=f)
        d.vf = [("speed", f"setpts=PTS/{f:g}")]
        d.af = [f"atempo={f:g}"] if c.has_audio else []
        d.spec = {
            "time": {"start_s": None, "end_s": round(c.duration_s / f, 3), "tolerance_s": 0.2}
        }
        d.slots = {"f": f"{f:g}"}
    else:
        fps = rng.choice([24, 25, 30, 60])
        if c.fps and abs(c.fps - fps) < 0.5:
            return None
        d = Draft(["F12"], [c.id], ["f12.fps"])
        d.vf, d.spec, d.slots = [("fps", f"fps={fps}")], {"video": {"fps": fps}}, {"fps": str(fps)}
    return d
