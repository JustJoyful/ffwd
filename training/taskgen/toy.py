"""Toy F1 trim tasks for the Phase 0 GRPO throughput spike (split "toy").

Generated from templates so they never overlap the hand-written spike-v0 dev tasks; their only
purpose is to measure GPU-hours per GRPO step, not to train a usable model.
"""

import random

# (clip id, duration in seconds) from the synthetic corpus
CLIPS = [("h264_long", 20), ("h264_25fps_720p", 10)]
TEMPLATES = [
    "toy: keep seconds {s} through {e}",
    "toy: I want just the section between {s}s and {e}s",
    "toy: trim it so only {s} to {e} seconds remain",
    "toy: extract the bit from second {s} up to second {e}",
]


def make_toy_tasks(n: int = 16, seed: int = 0) -> list[dict]:
    rng = random.Random(seed)
    tasks = []
    for i in range(n):
        clip, dur = rng.choice(CLIPS)
        start = rng.randint(1, dur - 4)
        end = rng.randint(start + 2, min(dur - 1, start + 8))
        run = {
            "action": "run",
            "inputs": [clip],
            "outputs": ["out1"],
            "args": [
                "-ss",
                str(start),
                "-i",
                f"{{in:{clip}}}",
                "-t",
                str(end - start),
                "-c",
                "copy",
                "{out:out1}",
            ],
        }
        tasks.append(
            {
                "id": f"toy-{seed}-{i:03d}",
                "split": "toy",
                "source": "toy-v0",
                "request": rng.choice(TEMPLATES).format(s=start, e=end),
                "inputs": [clip],
                "gold_spec": {
                    "family": ["F1"],
                    "outputs": [
                        {
                            "id": "out1",
                            "kind": "video",
                            "container": "mp4",
                            "time": {"start_s": start, "end_s": end, "tolerance_s": 0.15},
                        }
                    ],
                },
                "families": ["F1"],
                "difficulty": 1,
                "flags": {"ambiguous": False, "unsupported": False},
                "clarification": None,
                "reference_runs": [run],
            }
        )
    return tasks
