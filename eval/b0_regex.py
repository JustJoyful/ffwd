"""B0: a regex/preset baseline in the spirit of Ez FFmpeg (EVALUATION §3), run through the SAME harness.

About 20 hand-written patterns recognise common phrasings, fill a `Plan`, and one FFmpeg command is
assembled from it (operations combine, so multi-step requests can match). It has no ask_user, no
repair step and no understanding: unmatched requests get `unsupported`, a failed check gets
`unsupported` too (a preset tool cannot repair).

Honesty note: patterns were written by the same person who wrote the dev tasks, so B0 on `dev`
is likely optimistic for unseen phrasings. It is a dev-only baseline (RULES §4.5).
"""

import json
import re
from dataclasses import dataclass, field

NUM = r"(\d+(?:\.\d+)?)"
TIME = r"(\d+(?::\d{2}){1,2}(?:\.\d+)?|\d+(?:\.\d+)?)"
SEC = r"\s*(?:s|sec|secs|seconds?)\b"
H264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]


def _secs(t: str) -> float:
    total = 0.0
    for part in t.split(":"):
        total = total * 60 + float(part)
    return total


def _fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


@dataclass
class Plan:
    ss: float | None = None
    t: float | None = None
    vf: list[str] = field(default_factory=list)
    af: list[str] = field(default_factory=list)
    reencode: bool = False
    an: bool = False
    audio_only_mp3: bool = False
    gif_width: int | None = None
    frames: str | None = None  # fps expression, or "first" for a single frame
    jpg: bool = False
    out_fps: float | None = None
    display_rotation: int | None = None  # lossless metadata rotation
    audio_shift_s: float | None = None
    merge: bool = False
    target_bytes: float | None = None


def _trim(req: str, plan: Plan, duration: float) -> None:
    if m := re.search(r"\b(?:cut|trim|chop|remove|drop|skip)\b[^.]*?\bfirst\s+" + NUM + SEC, req):
        plan.ss = float(m[1])
    elif (m := re.search(r"\blast\s+" + NUM + SEC, req)) and re.search(
        r"\b(?:only|keep|just|need|want)\b", req
    ):
        plan.ss = max(duration - float(m[1]), 0)
    elif m := re.search(r"\b(?:keep|only|just)\b[^.]*?\bfirst\s+" + NUM + SEC, req):
        plan.t = float(m[1])
    rng = re.search(
        r"(?:keep|from|between|seconds?|section|part|only|of|trim|cut|extract)\b\D{0,20}?"
        + TIME
        + r"\s*(?:s|sec\w*)?\s*(?:to|-|–|through|until|and)\s*"
        + TIME,
        req,
    )
    if rng and not re.search(r"\d+p\b|\d+\s*fps", rng[0]):
        start, end = _secs(rng[1]), _secs(rng[2])
        if end > start:
            plan.ss, plan.t = start, end - start


def _video_ops(req: str, plan: Plan) -> None:
    if re.search(r"\bgif\b", req):
        m = re.search(r"(\d+)\s*(?:px|pixels?)\s*wide", req)
        plan.gif_width = int(m[1]) if m else 480
        if m2 := re.search(r"\bfirst\s+" + NUM + SEC, req):
            plan.ss, plan.t = None, float(m2[1])
        return
    if m := re.search(r"\bevery\s+" + NUM + SEC, req):
        plan.frames = f"1/{_fmt(float(m[1]))}"
    elif re.search(r"\b(?:every|each|per|for every)\s+second\b", req):
        plan.frames = "1"
    elif re.search(r"\bfirst frame\b", req):
        plan.frames = "first"
    if plan.frames:
        plan.jpg = bool(re.search(r"\bjpe?g\b", req))
        return
    if re.search(r"\bmp3\b", req) and re.search(
        r"\b(?:save|extract|export|get|rip|as|audio)\b", req
    ):
        plan.audio_only_mp3 = True
        return
    if re.search(
        r"\b(?:remove|strip|drop|delete|mute|without|get rid of|no)\b[^.]{0,20}\b(?:sound|audio)\b"
        r"|don'?t need the (?:sound|audio)",
        req,
    ):
        plan.an = True
    size = re.search(r"\b(\d{3,4})\s*(?:x|by|×)\s*(\d{3,4})\b", req)
    if re.search(r"\b(?:vertical|portrait|9:16)\b", req):
        w, h = (int(size[1]), int(size[2])) if size else (1080, 1920)
        plan.vf += [f"scale={w}:{h}:force_original_aspect_ratio=increase", f"crop={w}:{h}"]
    elif re.search(r"\bsquare\b|\b1:1\b", req):
        plan.vf += ["crop=min(iw\\,ih):min(iw\\,ih)"]
        if size:
            plan.vf += [f"scale={size[1]}:{size[2]}"]
    elif size:
        plan.vf += [f"scale={size[1]}:{size[2]}"]
    elif m := re.search(r"\b(\d{3,4})p\b", req):
        plan.vf += [f"scale=-2:{m[1]}"]
    if re.search(r"\b(?:rotate|turn)\b|upside down", req):
        lossless = bool(
            re.search(
                r"lossless|without (?:losing|re-?encod)|no re-?encod|don'?t re-?encode|quality", req
            )
        )
        if re.search(r"180|upside down", req):
            if lossless:
                plan.display_rotation = 180
            else:
                plan.vf += ["hflip", "vflip"]
        else:
            ccw = bool(re.search(r"\b(?:left|counter|anti|ccw)", req))
            if lossless:
                plan.display_rotation = 90 if ccw else -90
            else:
                plan.vf += ["transpose=2" if ccw else "transpose=1"]
    elif re.search(r"\b(?:flip|mirror)\b", req):
        plan.vf += ["vflip" if re.search(r"vertical", req) else "hflip"]
    if m := re.search(r"\b" + NUM + r"\s*fps\b", req):
        plan.out_fps = float(m[1])
    f = None
    if m := re.search(NUM + r"\s*x\b", req):
        f = float(m[1])
    elif re.search(r"half speed|slow(?:er)? down|slow motion", req):
        f = 0.5
    elif re.search(r"double speed", req):
        f = 2.0
    if f and re.search(r"\b(?:speed|faster|slow|play)", req):
        plan.vf += [f"setpts=PTS/{_fmt(f)}"]
        plan.af += [f"atempo={_fmt(f)}"]
    if re.search(
        r"\b(?:won'?t|doesn'?t|can'?t|not)\s+(?:play|open|work)|compatib|plays? everywhere|something normal"
        r"|(?:convert|turn)\b.{0,25}\b(?:mp4|avi|webm|mov|hevc|iphone)",
        req,
    ):
        plan.reencode = True


def _audio_ops(req: str, plan: Plan) -> None:
    if re.search(r"normali[sz]e|loudness|lufs", req):
        lufs = re.search(r"(-\d+(?:\.\d+)?)\s*lufs", req)
        plan.af += [f"loudnorm=I={lufs[1] if lufs else '-16'}:TP=-1.5:LRA=11"]
    elif re.search(r"\b(?:boost|increase|raise|turn up|louder|amplify)\b", req):
        db = re.search(NUM + r"\s*db\b", req)
        plan.af += [f"volume={_fmt(float(db[1])) if db else '10'}dB"]
    if re.search(r"\b(?:behind|late|lag\w*|delay|early|ahead)\b", req) and re.search(
        r"\b(?:audio|sound)\b", req
    ):
        amt = 0.5 if re.search(r"half a second", req) else None
        if m := re.search(NUM + r"\s*(ms|milliseconds?|s|sec\w*)\b", req):
            amt = float(m[1]) / (1000 if m[2].startswith("m") else 1)
        if amt is not None:
            behind = bool(re.search(r"\b(?:behind|late|lag\w*)\b", req))
            advance = behind and not re.search(r"delay the (?:audio|sound)", req)
            plan.audio_shift_s = -amt if advance else amt


def _size(req: str, plan: Plan) -> None:
    if m := re.search(
        r"(?:under|below|smaller than|less than|within|at most|max(?:imum)?|<)\s*"
        + NUM
        + r"\s*(mb|megabytes?|kb)\b",
        req,
    ):
        plan.target_bytes = float(m[1]) * (1e6 if m[2].startswith("m") else 1e3)


def plan_command(request: str, inputs: list[dict], out_id: str) -> dict | None:
    """The `run` action for a request, or None if no pattern matched."""
    req = request.lower()
    first = inputs[0]["probe"]
    duration = float(first.get("duration_s") or 0)
    has_audio = any(s["type"] == "audio" for s in first["streams"])
    plan = Plan()
    plan.merge = len(inputs) >= 2 and bool(
        re.search(
            r"\b(?:merge|combine|join|concat\w*|stitch|back to back|together|one video)\b", req
        )
    )
    _trim(req, plan, duration)
    _video_ops(req, plan)
    _audio_ops(req, plan)
    _size(req, plan)
    matched = any(
        [
            plan.ss is not None,
            plan.t,
            plan.vf,
            plan.af,
            plan.an,
            plan.audio_only_mp3,
            plan.gif_width,
            plan.frames,
            plan.out_fps,
            plan.display_rotation is not None,
            plan.audio_shift_s is not None,
            plan.merge,
            plan.target_bytes,
            plan.reencode,
        ]
    )
    if not matched:
        return None
    if not has_audio:
        plan.af = []
    ids = [i["id"] for i in inputs]
    out = f"{{out:{out_id}}}"

    def inp(i: str) -> list[str]:
        return ["-i", f"{{in:{i}}}"]

    args: list[str] = []

    if plan.merge:
        n = len(ids)
        audio = not plan.an and all(
            any(s["type"] == "audio" for s in i["probe"]["streams"]) for i in inputs
        )
        for i in ids:
            args += inp(i)
        pads = "".join(f"[{k}:v][{k}:a]" if audio else f"[{k}:v]" for k in range(n))
        graph = f"{pads}concat=n={n}:v=1:a={1 if audio else 0}[v]" + ("[a]" if audio else "")
        args += ["-filter_complex", graph, "-map", "[v]"] + (["-map", "[a]"] if audio else [])
        args += H264 + (["-c:a", "aac"] if audio else [])
        return {"action": "run", "args": args + [out], "inputs": ids, "outputs": [out_id]}

    if plan.audio_shift_s is not None:
        # The audio comes from a second, time-shifted open of the same file (negative = advance).
        args += inp(ids[0]) + ["-itsoffset", _fmt(plan.audio_shift_s)] + inp(ids[0])
        args += ["-map", "0:v", "-map", "1:a", "-c", "copy"]
        return {"action": "run", "args": args + [out], "inputs": [ids[0]], "outputs": [out_id]}

    if plan.display_rotation is not None:
        args += ["-display_rotation", _fmt(plan.display_rotation)]
    if plan.ss is not None:
        args += ["-ss", _fmt(plan.ss)]
    args += inp(ids[0])
    if plan.t:
        args += ["-t", _fmt(plan.t)]

    if plan.gif_width:
        graph = f"fps=10,scale={plan.gif_width}:-1,split[x][y];[x]palettegen[p];[y][p]paletteuse"
        args += ["-filter_complex", graph]
    elif plan.frames:
        if plan.frames == "first":
            args += ["-frames:v", "1"]
        else:
            args += ["-vf", f"fps={plan.frames}"] + (["-q:v", "2"] if plan.jpg else [])
    elif plan.audio_only_mp3:
        args += ["-vn", "-c:a", "libmp3lame", "-b:a", "192k"]
    else:
        reencode_video = bool(plan.vf or plan.out_fps or plan.target_bytes or plan.reencode)
        if plan.vf:
            args += ["-vf", ",".join(plan.vf)]
        if plan.af:
            args += ["-af", ",".join(plan.af)]
        if plan.out_fps:
            args += ["-r", _fmt(plan.out_fps)]
        if plan.target_bytes:
            length = plan.t or max(duration - (plan.ss or 0), 1)
            vb = max(int(plan.target_bytes * 8 * 0.9 / length / 1000) - 64, 100)
            args += [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-b:v",
                f"{vb}k",
                "-maxrate",
                f"{vb}k",
            ]
            args += ["-bufsize", f"{2 * vb}k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k"]
        else:
            if not reencode_video and not plan.af:
                args += ["-c:v", "copy"] if plan.an else ["-c", "copy"]
            else:
                args += H264 if reencode_video else ["-c:v", "copy"]
                args += ["-c:a", "aac"] if plan.af or plan.reencode else ["-c:a", "copy"]
            if plan.reencode:
                args += ["-movflags", "+faststart"]
        if plan.an:
            args += ["-an"]
    return {"action": "run", "args": args + [out], "inputs": [ids[0]], "outputs": [out_id]}


class RegexPolicy:
    """A loop Policy: one `run` from the first message, `finish` after a passing check, else give up."""

    def __call__(self, messages: list[dict]) -> str:
        if len(messages) == 2:
            first = json.loads(messages[1]["content"])
            inputs = [{"id": i["id"], "probe": i["probe"]} for i in first["inputs"]]
            action = plan_command(first["request"], inputs, first["outputs"][0])
            if action is None:
                return json.dumps(
                    {"action": "unsupported", "reason": "no preset matches this request"}
                )
            return json.dumps(action)
        obs = json.loads(messages[-1]["content"])
        checks = obs.get("checks") or {}
        if obs.get("run_ok") and checks and all(c["passed"] for c in checks.values()):
            return json.dumps(
                {"action": "finish", "outputs": list(checks), "note": "preset applied"}
            )
        return json.dumps({"action": "unsupported", "reason": "preset output did not pass"})
