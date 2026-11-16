"""Request phrasing for TRAIN-side styles (D-027). Held-out styles live in phrasing_heldout.py and are imported
ONLY by taskgen.build, so nothing that authors baselines or training data ever reads them.

An intent (e.g. "f1.cut_first") has standalone cores ("cut the first {n} seconds off this video"), continuation
forms for compositions ("then cut the first {n} seconds"), and symptom wordings. A STYLE wraps those: terse,
polite, verbose, symptom, casual_typos. Digits in slots appear verbatim in every rendering.
"""

import random

BANK: dict[str, dict[str, list[str]]] = {
    "f1.cut_first": {
        "core": [
            "cut the first {n} seconds off this video",
            "remove the first {n} seconds",
            "trim off the first {n} seconds of this clip",
            "drop the first {n} seconds",
        ],
        "cont": ["cut the first {n} seconds off", "drop the first {n} seconds"],
        "symptom": ["the first {n} seconds of this video are junk, get rid of them"],
    },
    "f1.keep_range": {
        "core": [
            "keep only the part from {s_mmss} to {e_mmss}",
            "keep seconds {s} to {e} and cut the rest",
            "trim this to {s}s through {e}s",
            "cut out the section between {s} and {e} seconds",
        ],
        "cont": ["keep only {s_mmss} to {e_mmss}", "trim it to {s} through {e} seconds"],
        "symptom": ["I only need the part between {s_mmss} and {e_mmss}"],
    },
    "f1.last_n": {
        "core": [
            "keep only the last {n} seconds of this clip",
            "cut everything except the final {n} seconds",
            "I only need the last {n} seconds",
        ],
        "cont": ["keep just the last {n} seconds", "cut it down to the final {n} seconds"],
        "symptom": ["only the last {n} seconds of this video matter, the rest is useless"],
    },
    "f1.first_n": {
        "core": [
            "keep just the first {n} seconds of this video",
            "cut this down to its first {n} seconds",
            "trim the clip to the first {n} seconds",
        ],
        "cont": ["keep just the first {n} seconds", "cut it to the first {n} seconds"],
        "symptom": ["I only want the first {n} seconds of this clip"],
    },
    "f2.merge": {
        "core": [
            "merge these {count} clips into one video",
            "join these {count} videos together in order",
            "put these {count} clips back to back in one file",
            "combine all {count} videos into a single video",
        ],
        "cont": ["merge them into one video", "join them back to back"],
        "symptom": ["I have {count} separate clips and need them as one video"],
    },
    "f2.merge_same_size": {
        "core": [
            "put these clips back to back in a single MP4, same size as the originals",
            "merge the clips into one video and keep the 1280x720 size",
            "join these videos into one file without changing the resolution",
        ],
        "cont": ["merge them into one video at the original size"],
        "symptom": ["I need these clips joined into one video, but nothing resized"],
    },
    "f3.iphone": {
        "core": [
            "convert this {fmt} iPhone video so it plays everywhere",
            "make this iPhone video work in PowerPoint",
            "turn this iPhone clip into a normal MP4 that plays on any device",
        ],
        "cont": ["convert it so it plays everywhere", "make it play in PowerPoint"],
        "symptom": [
            "this iPhone video won't play in PowerPoint",
            "my {fmt} video from the iPhone won't open on my friend's laptop",
        ],
    },
    "f3.webm": {
        "core": [
            "convert this .webm file to an MP4 that plays normally",
            "turn this WebM into a regular MP4",
            "make this webm video playable on my TV",
        ],
        "cont": ["convert it to a regular MP4", "make it playable on a TV"],
        "symptom": [
            "my TV won't play this .webm file",
            "this webm video doesn't open in my video editor",
        ],
    },
    "f3.avi": {
        "core": [
            "convert this old AVI into an MP4 that plays everywhere",
            "turn this AVI file into a modern MP4",
            "make this avi playable on my phone",
        ],
        "cont": ["convert it into an MP4 that plays everywhere", "turn it into a modern MP4"],
        "symptom": ["this old AVI won't play on my phone"],
    },
    "f3.prores": {
        "core": [
            "convert this ProRes file to a normal MP4",
            "turn this ProRes video into something that plays everywhere",
            "make this ProRes clip small enough to share as an MP4",
        ],
        "cont": ["convert it to a normal MP4", "turn it into something that plays everywhere"],
        "symptom": ["this ProRes file won't open on most computers"],
    },
    "f3.mkv": {
        "core": [
            "convert this MKV to an MP4",
            "turn this mkv file into an mp4 without losing quality",
            "put this MKV video in an MP4 container",
        ],
        "cont": ["convert it to an MP4", "put it in an MP4 container"],
        "symptom": ["my TV doesn't accept .mkv files"],
    },
    "f4.height": {
        "core": ["shrink this video to {h}p", "scale this down to {h}p", "make this video {h}p"],
        "cont": ["shrink it to {h}p", "scale it down to {h}p"],
        "symptom": ["this video is too high resolution, I want it at {h}p"],
    },
    "f4.width": {
        "core": [
            "make this video {w} pixels wide and keep the aspect ratio",
            "resize this clip to a width of {w}",
            "scale this to {w} px wide",
        ],
        "cont": ["make it {w} pixels wide", "resize it to a width of {w}"],
        "symptom": ["this video is too wide for my page, it needs to be {w} pixels wide"],
    },
    "f4.vertical": {
        "core": [
            "make it vertical, {w} by {h}",
            "turn this into a vertical {w}x{h} video for my phone",
            "reformat this for a phone screen, {w}x{h}",
        ],
        "cont": ["make it vertical, {w} by {h}", "reformat it to {w}x{h}"],
        "symptom": ["this is landscape but I need it vertical, {w}x{h}"],
    },
    "f4.square": {
        "core": [
            "make it a square video, {w} x {h}",
            "crop this to a {w}x{h} square",
            "turn this into a square clip at {w} by {h}",
        ],
        "cont": ["make it a square, {w} x {h}", "crop it to a {w}x{h} square"],
        "symptom": ["I need this as a square video, {w} x {h}, for a post"],
    },
    "f5.cw": {
        "core": [
            "rotate this video 90 degrees clockwise",
            "turn this video to the right",
            "rotate it a quarter turn clockwise",
        ],
        "cont": ["rotate it 90 degrees clockwise", "turn it to the right"],
        "symptom": ["this video is sideways, rotate it 90 degrees clockwise"],
    },
    "f5.ccw": {
        "core": [
            "rotate this video 90 degrees counterclockwise",
            "turn this video 90 degrees to the left",
            "rotate it a quarter turn to the left",
        ],
        "cont": ["rotate it 90 degrees counterclockwise", "turn it to the left"],
        "symptom": ["this video is sideways, turn it 90 degrees to the left"],
    },
    "f5.flip": {
        "core": [
            "flip this video upside down the right way up",
            "rotate this video 180 degrees",
            "turn this video around 180 degrees",
        ],
        "cont": ["rotate it 180 degrees", "flip it the right way up"],
        "symptom": ["this video is upside down, fix it"],
    },
    "f5.cw_lossless": {
        "core": [
            "rotate this 90 degrees clockwise without losing quality",
            "turn this video to the right without re-encoding",
            "rotate this video 90 degrees clockwise, lossless",
        ],
        "cont": ["rotate it 90 degrees clockwise without re-encoding"],
        "symptom": [
            "this video is sideways, rotate it 90 degrees clockwise but don't lose quality"
        ],
    },
    "f5.ccw_lossless": {
        "core": [
            "rotate this 90 degrees counterclockwise without losing quality",
            "turn this video to the left without re-encoding",
            "rotate this video 90 degrees to the left, lossless",
        ],
        "cont": ["rotate it 90 degrees counterclockwise without re-encoding"],
        "symptom": ["this video is sideways, turn it 90 degrees to the left without re-encoding"],
    },
    "f5.flip_lossless": {
        "core": [
            "flip this video the right way up without re-encoding",
            "rotate this video 180 degrees without losing quality",
            "this is upside down, flip it without re-encoding",
        ],
        "cont": ["rotate it 180 degrees without re-encoding"],
        "symptom": ["this video is upside down, fix it without re-encoding"],
    },
    "f6.size": {
        "core": [
            "make this video smaller than {mb} MB",
            "compress this to under {mb} MB",
            "shrink the file size to less than {mb} MB",
        ],
        "cont": ["make it smaller than {mb} MB", "compress it to under {mb} MB"],
        "symptom": [
            "I need to email this but it has to be under {mb} MB",
            "this file is too big to upload, it must be below {mb} MB",
        ],
    },
    "f6.size_keep_res": {
        "core": [
            "make the file under {mb} MB but keep it {res}",
            "compress this to less than {mb} MB without changing the resolution ({res})",
            "get this below {mb} MB and leave the resolution at {res}",
        ],
        "cont": ["make it under {mb} MB but keep it {res}"],
        "symptom": ["this is too big, get it under {mb} MB but keep {res}"],
    },
    "f7.interval": {
        "core": [
            "take a frame every {iv} seconds and save them as {fmt} images",
            "export one {fmt} picture every {iv} seconds",
            "grab a still every {iv} seconds as {fmt}",
        ],
        "cont": ["export one {fmt} picture every {iv} seconds"],
        "symptom": ["I need still images from this video, one every {iv} seconds, as {fmt}"],
    },
    "f7.first_frame": {
        "core": [
            "grab just the first frame as a {fmt} picture",
            "save the first frame of this video as an image ({fmt})",
            "give me a thumbnail from the very start as {fmt}",
        ],
        "cont": ["save the first frame as {fmt}"],
        "symptom": ["I need a thumbnail of this video's first frame, as {fmt}"],
    },
    "f8.whole": {
        "core": [
            "turn this clip into a small GIF, {w} pixels wide",
            "make a GIF of the whole video, {w}px wide",
            "convert this video to a {w} pixel wide GIF",
        ],
        "cont": ["turn it into a GIF, {w} pixels wide"],
        "symptom": ["I want to post this as a GIF, {w} pixels wide"],
    },
    "f8.range": {
        "core": [
            "make a {w}px wide GIF of {s_mmss} to {e_mmss}",
            "turn seconds {s} to {e} into a GIF, {w} pixels wide",
            "GIF of the part from {s} to {e} seconds, {w}px wide",
        ],
        "cont": ["make a {w}px wide GIF of {s_mmss} to {e_mmss}"],
        "symptom": ["I want just {s} to {e} seconds as a {w} pixel wide GIF"],
    },
    "f9.mp3": {
        "core": [
            "save the audio as an MP3",
            "extract the audio from this video as an mp3",
            "give me just the sound as an MP3 file",
        ],
        "cont": ["save the audio as an MP3", "extract the audio as an MP3"],
        "symptom": ["I only need the audio from this video, as an MP3"],
    },
    "f9.remove": {
        "core": [
            "remove the sound from this video",
            "strip the audio out of this clip",
            "make this video silent",
        ],
        "cont": ["remove the sound", "strip the audio out"],
        "symptom": ["the audio on this video is annoying, take it out"],
    },
    "f10.normalize": {
        "core": [
            "normalize the audio to {lufs} LUFS",
            "set the loudness of this video to {lufs} LUFS",
            "level the sound to {lufs} LUFS",
        ],
        "cont": ["normalize the audio to {lufs} LUFS", "set the loudness to {lufs} LUFS"],
        "symptom": ["the volume on this video is all over the place, normalize it to {lufs} LUFS"],
    },
    "f10.boost": {
        "core": [
            "boost the volume by {db} dB",
            "make this video {db} dB louder",
            "turn the sound up by {db} dB",
        ],
        "cont": ["boost the volume by {db} dB", "make it {db} dB louder"],
        "symptom": ["this video is too quiet, make it {db} dB louder"],
    },
    "f11.delay": {
        "core": [
            "delay the audio by {ms} ms",
            "make the sound come {ms} milliseconds later",
            "push the audio back by {sec} seconds",
        ],
        "cont": ["delay the audio by {ms} ms"],
        "symptom": ["the sound comes {sec} seconds too early, delay it"],
    },
    "f11.advance": {
        "core": [
            "move the audio {ms} ms earlier",
            "make the sound come {ms} milliseconds sooner",
            "advance the audio by {sec} seconds",
        ],
        "cont": ["move the audio {ms} ms earlier"],
        "symptom": ["the audio is {sec} seconds behind the video, move it earlier"],
    },
    "f11.fix_late": {
        "core": [
            "the audio is half a second behind the video, fix it",
            "fix the sound: it plays {ms} ms after the picture",
            "re-sync this video, the audio starts {ms} milliseconds late",
        ],
        "cont": ["fix the sync, the audio is half a second late"],
        "symptom": ["in this video the audio is half a second behind, it looks dubbed"],
    },
    "f11.fix_early": {
        "core": [
            "the audio is half a second ahead of the video, fix it",
            "fix the sound: it plays {ms} ms before the picture",
            "re-sync this video, the audio starts {ms} milliseconds early",
        ],
        "cont": ["fix the sync, the audio is half a second early"],
        "symptom": ["in this video the sound comes half a second before the picture"],
    },
    "f12.speed_up": {
        "core": [
            "speed this video up {f}x",
            "make this play {f} times faster",
            "make this video {f}x faster",
        ],
        "cont": ["speed it up {f}x", "make it {f}x faster"],
        "symptom": ["this video is too slow, make it {f}x faster"],
    },
    "f12.slow_down": {
        "core": [
            "slow this video down to {f}x speed",
            "make this play at {f}x speed",
            "play this at {f}x speed",
        ],
        "cont": ["slow it down to {f}x speed", "make it play at {f}x speed"],
        "symptom": ["this goes by too fast, slow it to {f}x speed"],
    },
    "f12.fps": {
        "core": [
            "convert this to {fps} fps",
            "change the frame rate of this video to {fps} fps",
            "make this {fps} fps",
        ],
        "cont": ["convert it to {fps} fps", "change the frame rate to {fps} fps"],
        "symptom": ["this needs to be {fps} fps for my editor"],
    },
}

TRAIN_STYLES = ("terse", "polite", "verbose", "symptom", "casual_typos")
_POLITE = ["could you please {c}?", "please {c}", "can you {c}?", "I'd like you to {c}, thanks"]
_PRE = [
    "I have a video on my laptop and I want to ",
    "so I recorded this clip and I need to ",
    "I've got a file here and I'd like to ",
]
_POST = ["", " thanks!", ", that's all I need.", " it's for a school project."]
_JOIN = [" and ", ", then ", " and then "]


def typo(text: str, rng: random.Random, p: float = 0.35) -> str:
    """Drop or swap letters in some alphabetic words of length >= 5; digits and short words are untouched."""
    out = []
    for w in text.split(" "):
        if len(w) >= 5 and w.isalpha() and rng.random() < p:
            i = rng.randrange(1, len(w) - 1)
            w = w[:i] + w[i + 1] + w[i] + w[i + 2 :] if rng.random() < 0.5 else w[:i] + w[i + 1 :]
        out.append(w)
    return " ".join(out)


def _cores(intents: list[str], slots: dict, rng: random.Random, key: str = "core") -> str:
    parts = []
    for i, it in enumerate(intents):
        forms = BANK[it]["cont" if i and key == "core" else key]
        parts.append(rng.choice(forms).format(**slots))
    return rng.choice(_JOIN).join(parts) if len(parts) > 1 else parts[0]


def render_request(intents: list[str], slots: dict, style: str, rng: random.Random) -> str:
    if style == "terse":
        return _cores(intents, slots, rng)
    if style == "polite":
        return rng.choice(_POLITE).format(c=_cores(intents, slots, rng))
    if style == "verbose":
        c = _cores(intents, slots, rng)
        return rng.choice(_PRE) + c + rng.choice(_POST)
    if style == "symptom":
        first = rng.choice(BANK[intents[0]]["symptom"]).format(**slots)
        rest = [rng.choice(BANK[i]["cont"]).format(**slots) for i in intents[1:]]
        return first + ("".join(f", and {r}" for r in rest) if rest else "")
    if style == "casual_typos":
        return typo(_cores(intents, slots, rng).lower(), rng)
    from training.taskgen import (
        phrasing_heldout,
    )  # noqa: PLC0415  (isolated on purpose, see module docstring)

    return phrasing_heldout.render(intents, slots, style, rng)
