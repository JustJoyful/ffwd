"""Build SFT examples from kept teacher (and optional rejection-sampled) trajectories.

uv run --group train python -m training.sft.build --teacher data/sft/teacher-v1/kept.jsonl [--rejection ...] --out data/sft
Reads TRAIN tasks' trajectories only (their ids start with 'tr-'); refuses anything else.
"""

import argparse
import json
from pathlib import Path

from transformers import AutoTokenizer

from training import config
from training.env.chat_template import install
from training.sft import dataset as ds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", type=Path, required=True)
    ap.add_argument("--rejection", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-0.6B")
    a = ap.parse_args()
    tok = install(AutoTokenizer.from_pretrained(a.model))
    ts, rs = ds.load_trajectories(a.teacher), (
        ds.load_trajectories(a.rejection) if a.rejection else []
    )
    for rec in [*ts, *rs]:
        if not rec["task_id"].startswith("tr-"):
            raise SystemExit(f"{rec['task_id']} is not a train task: refusing (RULES §4.5)")
    teacher, st1 = ds.build_examples(ts, tok)
    rejection, st2 = ds.build_examples(rs, tok) if rs else ([], {})
    mixed = ds.mix(teacher, rejection)
    keys = {
        t["id"]: t["content_key"]
        for t in (
            json.loads(x)
            for x in (config.DATA_DIR / "tasks" / "train" / "v1.jsonl").read_text().splitlines()
        )
    }
    train, val = ds.validation_split(mixed, keys)
    a.out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("examples.jsonl", train), ("val.jsonl", val)):
        (a.out / name).write_text(
            "".join(
                json.dumps({"input_ids": r["input_ids"], "labels": r["labels"]}) + "\n"
                for r in rows
            )
        )
    (a.out / "stats.json").write_text(
        json.dumps(
            {"teacher": st1, "rejection": st2, "train": ds.stats(train), "val": ds.stats(val)},
            indent=1,
        )
        + "\n"
    )
    print((a.out / "stats.json").read_text())


if __name__ == "__main__":
    main()
