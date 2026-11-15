import json

import pytest

from eval.b0_regex import RegexPolicy, plan_command
from training.env.validator import validate_run


def inp(id="clip", dur=20.0, audio=True):
    streams = [{"index": 0, "type": "video", "codec": "h264", "width": 1280, "height": 720}]
    if audio:
        streams.append({"index": 1, "type": "audio", "codec": "aac"})
    return {"id": id, "probe": {"duration_s": dur, "streams": streams}}


def plan(request, inputs=None, out="out1"):
    return plan_command(request, inputs or [inp()], out)


def joined(args):
    return " ".join(args)


@pytest.mark.parametrize(
    "request_text,expected_fragments",
    [
        ("please cut the first 5 seconds off", ["-ss 5", "-c copy"]),
        ("I just want the last 4 seconds", ["-ss 16", "-c copy"]),
        ("keep 1:10 to 1:25", ["-ss 70", "-t 15"]),
        ("extract the part between 3s and 9s", ["-ss 3", "-t 6"]),
        ("save the audio as mp3", ["-vn", "libmp3lame"]),
        ("get rid of the audio track", ["-an", "-c:v copy"]),
        ("scale it down to 480p", ["scale=-2:480"]),
        ("make this a vertical video", ["scale=1080:1920"]),
        ("crop to a 1:1 square", ["crop=min(iw\\,ih)"]),
        ("resize to 640x360", ["scale=640:360"]),
        ("rotate it 90 degrees to the right", ["transpose=1"]),
        ("rotate 90 degrees counter-clockwise", ["transpose=2"]),
        ("rotate 90 degrees clockwise, don't re-encode", ["-display_rotation", "-c copy"]),
        ("flip the video horizontally", ["hflip"]),
        ("shrink the file to under 5 MB", ["-b:v", "maxrate"]),
        ("my tv won't play this file", ["libx264", "yuv420p", "aac"]),
        ("change it to 24 fps", ["-r 24"]),
        ("make it play 3x faster", ["setpts=PTS/3", "atempo=3"]),
        ("slow it down to half speed", ["setpts=PTS/0.5", "atempo=0.5"]),
        ("boost the volume by 12 dB", ["volume=12dB"]),
        ("normalize the loudness to -14 LUFS", ["loudnorm=I=-14"]),
        ("the audio lags the picture by 300 ms", ["-itsoffset -0.3", "-map 1:a"]),
        ("delay the audio by 250 ms", ["-itsoffset 0.25"]),
        ("one frame every 4 seconds", ["fps=1/4"]),
        ("export a picture each second as jpg", ["fps=1", "-q:v 2"]),
        ("turn the first 3 seconds into a gif", ["-t 3", "palettegen"]),
    ],
)
def test_single_operations(request_text, expected_fragments):
    action = plan(request_text)
    assert action is not None, request_text
    text = joined(action["args"])
    for frag in expected_fragments:
        assert frag in text, (frag, text)


def test_every_plan_passes_the_allowlist_validator():
    for r in [
        "cut the first 5 seconds",
        "scale it down to 480p",
        "rotate it 90 degrees to the right",
        "shrink the file to under 5 MB",
        "make it play 3x faster",
        "delay the audio by 250 ms",
        "turn the first 3 seconds into a gif",
        "crop to a square",
        "boost the volume by 12 dB",
    ]:
        a = plan(r)
        v = validate_run(
            a["args"], a["inputs"], a["outputs"], known_inputs={"clip"}, known_outputs={"out1"}
        )
        assert v.ok, (r, v.reason)


def test_multi_step_requests_combine_operations_in_one_command():
    a = plan("keep 0:02 to 0:08, make it 720p and under 3 MB")
    t = joined(a["args"])
    assert "-ss 2" in t and "-t 6" in t and "scale=-2:720" in t and "-b:v" in t
    # bitrate budget uses the TRIMMED duration (6 s), not the 20 s input
    vb = (
        int(a["args"][a["args"].index("-b:v") + 1].rstrip("k"))
        if a["args"][a["args"].index("-b:v") + 1].endswith("k")
        else None
    )
    assert vb is not None and vb > 2000


def test_merge_uses_all_inputs_and_drops_audio_when_asked():
    a = plan_command("join these clips into one, no sound", [inp("a"), inp("b")], "out1")
    t = joined(a["args"])
    assert (
        a["inputs"] == ["a", "b"]
        and "concat=n=2:v=1:a=0" in t
        and "-map [v]" in t
        and "[a]" not in t
    )
    b = plan_command("combine these two clips", [inp("a"), inp("b")], "out1")
    assert "concat=n=2:v=1:a=1" in joined(b["args"])


def test_unrecognised_requests_return_none():
    for r in [
        "remove the person walking in the background",
        "add subtitles",
        "make it look cinematic",
        "make it shorter",
        "fix this",
    ]:
        assert plan(r) is None, r


def test_speed_skips_audio_filter_when_input_has_no_audio():
    t = joined(plan_command("2x faster", [inp(audio=False)], "out1")["args"])
    assert "setpts=PTS/2" in t and "atempo" not in t


def test_policy_runs_then_finishes_on_pass_and_gives_up_on_fail():
    pol = RegexPolicy()
    first = json.dumps(
        {"request": "cut the first 5 seconds off", "inputs": [inp()], "outputs": ["out1"]}
    )
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": first}]
    run = json.loads(pol(msgs))
    assert run["action"] == "run"
    ok = {"run_ok": True, "checks": {"out1": {"passed": True, "failed": []}}}
    msgs += [{"role": "assistant", "content": "x"}, {"role": "user", "content": json.dumps(ok)}]
    assert json.loads(pol(msgs))["action"] == "finish"
    bad = {"run_ok": True, "checks": {"out1": {"passed": False, "failed": [{"field": "time"}]}}}
    msgs[-1] = {"role": "user", "content": json.dumps(bad)}
    assert json.loads(pol(msgs))["action"] == "unsupported"
    nomatch = json.dumps({"request": "add subtitles", "inputs": [inp()], "outputs": ["out1"]})
    assert (
        json.loads(
            RegexPolicy()(
                [{"role": "system", "content": "s"}, {"role": "user", "content": nomatch}]
            )
        )["action"]
        == "unsupported"
    )
