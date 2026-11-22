"""A3: M3 Q8_0 vs Q4_K_M on the SAME seeded 100 dev tasks (dev only; the Q8_0 side is an already published dev run).

uv run python -m eval.quant_parity --q8-run reports/2026-11-22-m3-ckpt60-dev/grpo-m3-ckpt60-q8 \
    --out reports/2026-11-22-m3-q4km-parity

Runs the Q4_K_M server on port 8081 (eval/configs/grpo-m3-ckpt60-q4km.toml) beside any other server, runs the harness on
the sample, then applies the shipping rule written BEFORE the run in `reports/2026-11-22-m3-q4km-parity/RULE.md`
(`decide` below is that rule in code; the two must say the same).
"""

import argparse
import json
from pathlib import Path

from eval import run_baseline
from eval.final_report import load, metric_values
from eval.hf_parity import sample_ids, turns
from eval.parity import parity
from eval.phase1_run import MODELS, ROOT, serve_gguf
from training.taskgen.loader import load_tasks

CFG = ROOT / "eval" / "configs" / "grpo-m3-ckpt60-q4km.toml"
GGUF = MODELS / "grpo-m3-ckpt60-gguf" / "grpo-m3-ckpt60-q4_k_m.gguf"
SEED, N = 20261115, 100


def decide(q8: dict, q4: dict, p: dict) -> dict:
    """The rule of RULE.md. `q8`/`q4`: {"invalid": episodes with an invalid turn, "runs": mean runs, "nof": needless-or-fail rate}."""
    checks = {
        "success within 2 pp and McNemar p > 0.05": p["b_minus_a"]["diff"] >= -0.02 and p["mcnemar_p"] > 0.05,
        "invalid-action episodes at most 2 more": q4["invalid"] <= q8["invalid"] + 2,
        "mean runs at most 0.05 higher": q4["runs"] <= q8["runs"] + 0.05,
        "needless-or-fail not higher": q4["nof"] <= q8["nof"],
    }  # fmt: skip
    return {"checks": checks, "ships": "Q4_K_M" if all(checks.values()) else "Q8_0"}


def side(run_dir: Path, tasks: dict[str, dict], ids: set[str]) -> dict:
    res, eps = load(run_dir)
    res, eps = ({i: v for i, v in d.items() if i in ids} for d in (res, eps))
    runs = metric_values("runs", tasks, res, eps)
    nof = metric_values("needless_or_fail", tasks, res, eps)
    return {
        "res": res, "eps": eps, "k": sum(bool(r["success"]) for r in res.values()),
        "invalid": sum(r["invalid_turns"] > 0 for r in res.values()),
        "runs": sum(runs.values()) / len(runs), "n_graded": len(runs),
        "nof": sum(nof.values()) / len(nof) if nof else 0.0, "n_copy_eligible": len(nof),
    }  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--q8-run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.joinpath("M3-q4km").exists():
        raise SystemExit("refusing to overwrite a run")
    all_tasks = load_tasks("dev", "dev-eval")  # dev only
    ids = set(sample_ids(all_tasks, N, SEED))
    tasks = {t["id"]: t for t in all_tasks if t["id"] in ids}
    a.out.mkdir(parents=True, exist_ok=True)
    subset = a.out / "sample-tasks.jsonl"
    subset.write_text("".join(json.dumps(t) + "\n" for t in all_tasks if t["id"] in ids))
    with serve_gguf(CFG, GGUF, a.out, "q4km"):
        run_baseline.main(["--system", "M3", "--model-config", str(CFG), "--tasks", str(subset),
                           "--out", str(a.out / "M3-q4km")])  # fmt: skip
    q8, q4 = side(a.q8_run, tasks, ids), side(a.out / "M3-q4km", tasks, ids)
    if set(q8["res"]) != set(q4["res"]) or len(q4["res"]) != N:
        raise SystemExit("task sets differ: refusing to compare")
    p = parity({i: bool(r["success"]) for i, r in q8["res"].items()}, {i: bool(r["success"]) for i, r in q4["res"].items()})  # fmt: skip
    t8, t4 = turns(a.q8_run), turns(a.out / "M3-q4km")
    p["first_turn_identical"] = sum(t8[i][:1] == t4[i][:1] for i in ids) / N
    p["transcript_identical"] = sum(t8[i] == t4[i] for i in ids) / N
    d = decide(
        {k: q8[k] for k in ("invalid", "runs", "nof")},
        {k: q4[k] for k in ("invalid", "runs", "nof")},
        p,
    )
    summary = {"sample_ids": sorted(ids), "parity_q8_a_vs_q4_b": p, "q8": {k: v for k, v in q8.items() if k not in ("res", "eps")}, "q4": {k: v for k, v in q4.items() if k not in ("res", "eps")}, "decision": d}  # fmt: skip
    (a.out / "parity.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "sample_ids"}, indent=1))


if __name__ == "__main__":
    main()
