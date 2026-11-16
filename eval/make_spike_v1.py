"""Derive data/tasks/dev/spike-v1.jsonl from spike-v0.jsonl (v0 is never modified).

uv run python -m eval.make_spike_v1

Every change is listed in CHANGES below and written to spike-v1.CHANGES.md. New tasks the owner writes
are appended later with source "spike-v1-new" and ids n01, n02, ... so "original vs new" is mechanical.
"""

import json

from training import config

TASKS = config.DATA_DIR / "tasks" / "dev"
DROP = {"m05-merge-mute": "duplicate of s06 (merge + remove sound)"}
UNSUPPORTED = ("u01-remove-person", "u02-add-subtitles", "u03-cinematic-grade")


def _frames(spec: dict, **frames) -> None:
    spec["outputs"][0]["frames"].update(frames)


def revise(task: dict) -> tuple[dict, list[str]]:
    t, notes = json.loads(json.dumps(task)), []
    tid = t["id"]
    if tid == "s13-rotate-cw-lossless":
        t["gold_spec"]["outputs"][0]["video"]["rotation"] = 90
        notes.append("video.rotation 270 -> 90: one clockwise convention (spec.schema.json)")
    if tid == "s15-turn-left":
        t["gold_spec"]["outputs"][0]["video"]["rotation"] = 270
        notes.append("added video.rotation 270 (90 counterclockwise): direction is now checked")
    if tid == "m09-rotate-cw-30fps":
        t["gold_spec"]["outputs"][0]["video"]["rotation"] = 90
        notes.append("added video.rotation 90 (clockwise): direction is now checked")
    if tid == "s19-frame-every-2s":
        _frames(t["gold_spec"], interval_s=2, expected_count=5)
        notes.append("frames: interval 2 + expected_count 5 (10 s clip, samples at 0,2,4,6,8)")
    if tid == "s20-every-second-jpg":
        _frames(t["gold_spec"], interval_s=1, expected_count=10)
        notes.append("frames: interval 1 + expected_count 10 (10 s clip, samples at 0..9)")
    if tid == "m03-frames-2-to-7":
        _frames(t["gold_spec"], interval_s=1, expected_count=5)
        notes.append("frames: interval 1 + expected_count 5 (window 2 s..7 s, samples at 2..6)")
    if tid in UNSUPPORTED:
        t["families"], t["nearest_supported"] = [], None
        notes.append(f"families {task['families']} -> [] ; nearest_supported null (nothing close)")
    return t, notes


def main() -> None:
    src = (TASKS / "spike-v0.jsonl").read_text().splitlines()
    out, changelog = [], []
    for line in src:
        task = json.loads(line)
        if task["id"] in DROP:
            changelog.append(f"- `{task['id']}`: DROPPED, {DROP[task['id']]}")
            continue
        new, notes = revise(task)
        out.append(new)
        changelog += [f"- `{task['id']}`: {n}" for n in notes]
    (TASKS / "spike-v1.jsonl").write_text("".join(json.dumps(t) + "\n" for t in out))
    head = (
        "# spike-v1 changes relative to spike-v0\n\n"
        f"{len(src)} v0 tasks -> {len(out)} carried over (new tasks are added separately, ids n01..).\n"
        "Invariants (output duration and audio presence must match the input unless the spec changes them),\n"
        "the rotation convention and the frame-count rule are CHECKER changes (checker v1.2) that apply to\n"
        "all tasks; they need no per-task edits except where listed.\n\n"
    )
    (TASKS / "spike-v1.CHANGES.md").write_text(head + "\n".join(changelog) + "\n")
    print(f"wrote {len(out)} tasks")


if __name__ == "__main__":
    main()
