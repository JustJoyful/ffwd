"""Replay fixtures for the browser bench kit (ffwd-web spikes/bench-kit): 20 recorded dev episodes of the NATIVE Q5_K_M run.

    uv run python -m eval.make_bench_prompts --out ../ffwd-web/spikes/bench-kit/prompts.json

A friend's laptop has no repo, no corpus and no checker, so the kit cannot score task success. It replays these
episodes turn by turn (teacher-forced: the history is the recorded one) and measures how often the browser model
reproduces the recorded reply of the native llama.cpp b12032 run, how often its reply is a well-formed action, and how
fast it is. The first 20 ids of the seeded 100-task dev sample are used (dev only; no test data). The system prompt
is stored once; the page rebuilds every message list with the site's own chat-template renderer.
"""

import argparse
import json
from pathlib import Path

from eval.hf_parity import sample_ids
from eval.quant_parity import SEED, N
from eval.run_baseline import load_corpus
from training import config
from training.env.constrained import load_prompt
from training.env.loop import initial_messages
from training.env.probe import probe
from training.taskgen.loader import load_tasks

SOURCE = config.REPO_ROOT / "reports" / "2026-11-23-m3-q5km-parity" / "M3-q5km"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    all_tasks = load_tasks("dev", "dev-eval")  # dev only
    by_id = {t["id"]: t for t in all_tasks}
    ids = sample_ids(all_tasks, N, SEED)[: a.n]
    eps = {
        e["task_id"]: e
        for e in map(json.loads, (SOURCE / "episodes.jsonl").read_text().splitlines())
    }
    corpus, system = load_corpus(), load_prompt("system-v1.txt")
    episodes = []
    for tid in ids:
        t = by_id[tid]
        msgs = initial_messages(t, {c: probe(corpus[c]) for c in t["inputs"]}, system)
        assert msgs[0] == {"role": "system", "content": system} and len(msgs) == 2
        turns = [
            {"assistant": x["assistant"], "observation": json.dumps(x["observation"])}
            for x in eps[tid]["turns"]
        ]
        episodes.append({"task_id": tid, "user0": msgs[1]["content"], "turns": turns})
    out = {"system": system, "n": len(episodes), "n_turns": sum(len(e["turns"]) for e in episodes),
           "source": "native llama.cpp b12032, M3 GGUF Q5_K_M, greedy, reports/2026-11-23-m3-q5km-parity", "episodes": episodes}  # fmt: skip
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print(
        f"{out['n']} episodes, {out['n_turns']} turns -> {a.out} ({a.out.stat().st_size // 1024} KB)"
    )


if __name__ == "__main__":
    main()
