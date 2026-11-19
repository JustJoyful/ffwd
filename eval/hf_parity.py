"""HF fp16 vs GGUF Q8_0 on the SAME dev tasks (EVALUATION §6, plan T22). Dev only.

uv run python -m eval.hf_parity --model-dir data/models/m1-merged/ffmpeg-agent-m1-0.6b \
    --gguf-run reports/2026-11-20-m1-dev/M1-0.6b-q8 --n 100 --out reports/<date>-m1-parity

The GGUF side is NOT re-run: its per-task results are the already published dev run. The sample is fixed by seed
(sorted task ids, random.Random(seed).sample), so it is reproducible and not chosen by outcome. Besides the success
agreement (eval.parity) it reports transcript agreement: the share of tasks whose first assistant turn, and whose
whole sequence of assistant turns, is byte-identical on both sides (success can agree while text differs).
"""

import argparse
import hashlib
import json
import random
import tomllib
from pathlib import Path

from eval.hf_policy import HFPolicy
from eval.parity import load_results, parity
from eval.run_baseline import load_corpus, run_baseline
from training.env.constrained import load_prompt  # same loader the run_baseline CLI uses

CFG = Path(
    "eval/configs/m1-0.6b-q8.toml"
)  # the GGUF run's config: same prompt, protocol and run budget


def sample_ids(tasks: list[dict], n: int, seed: int) -> list[str]:
    return sorted(random.Random(seed).sample(sorted(t["id"] for t in tasks), n))


def turns(run_dir: Path) -> dict[str, list[str]]:
    """task_id -> assistant turn texts of a run (episodes.jsonl rows are in task order; results.jsonl has the ids)."""
    ids = [json.loads(x)["task_id"] for x in (run_dir / "results.jsonl").read_text().splitlines()]
    eps = [json.loads(x) for x in (run_dir / "episodes.jsonl").read_text().splitlines()]
    if len(ids) != len(eps):  # an errored episode writes a result but no transcript
        raise ValueError(f"{run_dir}: {len(ids)} results but {len(eps)} episodes")
    return {i: [t["assistant"] for t in e["turns"]] for i, e in zip(ids, eps, strict=True)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", type=Path, required=True)
    ap.add_argument("--gguf-run", type=Path, required=True)
    ap.add_argument("--tasks", type=Path, default=Path("data/tasks/dev/v1.jsonl"))
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20261115)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    raw = a.tasks.read_bytes()
    all_tasks = [json.loads(x) for x in raw.decode().splitlines()]
    if any(t["split"] != "dev" for t in all_tasks):
        raise SystemExit("the parity check reads dev tasks only")
    keep = set(sample_ids(all_tasks, a.n, a.seed))
    tasks = [t for t in all_tasks if t["id"] in keep]
    cfg = tomllib.loads(CFG.read_text())
    hf_dir = a.out / "M1-hf-fp16"
    run_baseline(
        system="M1",
        policy=HFPolicy(a.model_dir),
        tasks=tasks,
        out=hf_dir,
        corpus=load_corpus(),
        meta={"model": "ffmpeg-agent-m1-0.6b", "quant": "fp16 (HF transformers)", "temperature": 0.0,
              "model_config": str(CFG), "system_prompt": cfg["system_prompt"], "constrained_decoding": False,
              "require_spec": True, "stop_after_ask": True, "parity_sample_seed": a.seed},
        tasks_sha256=hashlib.sha256(raw).hexdigest(),
        system_prompt_text=load_prompt(cfg["system_prompt"]),
        require_spec=True,
        stop_after_ask=True,
    )  # fmt: skip
    gguf, hf = load_results(a.gguf_run), load_results(hf_dir)
    gguf = {i: gguf[i] for i in hf}  # the GGUF run covered all 300; compare on the sample
    out = parity(gguf, hf)  # a = GGUF, b = HF
    tg, th = turns(a.gguf_run), turns(hf_dir)
    out["first_turn_identical"] = sum(tg[i][:1] == th[i][:1] for i in hf) / len(hf)
    out["transcript_identical"] = sum(tg[i] == th[i] for i in hf) / len(hf)
    out["differing_tasks"] = sorted(i for i in hf if tg[i] != th[i])
    out["sample_ids"] = sorted(hf)
    (a.out / "parity.json").write_text(json.dumps(out, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in out.items() if k not in ("sample_ids", "differing_tasks")}, indent=1
        )
    )


if __name__ == "__main__":
    main()
