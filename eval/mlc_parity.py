"""MLC q4f16_1 parity on the SAME seeded 100 dev tasks as eval.quant_parity (dev only; the references are published dev runs).

    # 1. prompt fixtures (first turns of 10 sample tasks + one multi-turn transcript) for eval.mlc_prompt_identity
    uv run python -m eval.mlc_parity fixtures --out reports/<date>-mlc-parity/prompt-fixtures.json
    # 2. MLC weights -> fp16 HF dir (eval.mlc_dequant), then run the harness on that dir
    uv run --group train python -m eval.mlc_parity run --model-dir data/mlc/m3-q4f16_1-dequant --name M3-mlc-q4f16_1 \
        --ref-run reports/2026-11-22-m3-ckpt60-dev/grpo-m3-ckpt60-q8 --out reports/<date>-mlc-parity [--also LABEL=RUN_DIR ...]

The model runs through HF transformers fp16 with the agent chat template, greedy, 512 new tokens, same harness and run
budget as the llama-server runs (eval/hf_policy.py). It is a stand-in for the MLC runtime, which could not be built here:
it sees exactly the weights MLC stored (see eval/mlc_dequant.py) but not the WebGPU kernels' rounding.
Writes `<out>/<name>/` (results, episodes, manifest) and `<out>/<name>.parity.json`; refuses to overwrite.
"""

import argparse
import hashlib
import json
import re
import tomllib
from collections import Counter
from pathlib import Path

from eval.hf_parity import sample_ids, turns
from eval.parity import parity
from eval.quant_parity import SEED, N, side
from eval.run_baseline import load_corpus, run_baseline
from training import config
from training.env.constrained import load_prompt
from training.env.loop import initial_messages
from training.env.probe import probe
from training.taskgen.loader import load_tasks

CFG = config.REPO_ROOT / "eval" / "configs" / "mlc-q4f16_1-dequant.toml"


def classify(obs) -> str:
    """One label per turn from the observation the harness gave back (the turn-level taxonomy of the Q4_K_M analysis)."""
    if not isinstance(obs, dict):
        return "other"
    if err := obs.get("error"):
        for prefix, label in (
            ("reply is not a JSON", "malformed_json"),
            ("invalid action", "schema_invalid"),
        ):
            if err.startswith(prefix):
                return label
        return "run_before_spec" if "spec action first" in err else "other_error"
    if rej := obs.get("rejected"):
        if re.search(r"option not allowed: -y\b", rej):
            return "rejected:-y"
        return "rejected:option" if "option not allowed" in rej else "rejected:other"
    if obs.get("run_ok") is False:
        return "run_failed"
    if "checks" in obs and (
        obs.get("missing_outputs") or any(not c["passed"] for c in obs["checks"].values())
    ):
        return "check_failed"
    return "ok"


def taxonomy(eps: dict[str, dict], res: dict[str, dict]) -> dict:
    labels = [classify(t.get("observation")) for e in eps.values() for t in e["turns"]]
    first = Counter()
    for tid, r in res.items():
        if not r["success"]:
            bad = [b for b in (classify(t.get("observation")) for t in eps[tid]["turns"]) if b != "ok"] if tid in eps else ["no_episode"]  # fmt: skip
            first[bad[0] if bad else "check-failed-only"] += 1
    offending = Counter(
        m.group(1)
        for e in eps.values()
        for t in e["turns"]
        if isinstance(t.get("observation"), dict) and (m := re.search(r"option not allowed: (\S+)", t["observation"].get("rejected") or ""))  # fmt: skip
    )
    return {"turns": len(labels), "by_label": dict(Counter(labels)), "failed_episodes_first_problem": dict(first), "offending_options": offending.most_common(12)}  # fmt: skip


def fixtures(out: Path, n: int = 10) -> None:
    """First-turn messages of the first `n` sample tasks (sorted ids) + the first >=3-turn transcript of the reference run."""
    all_tasks = load_tasks("dev", "dev-eval")
    ids = sample_ids(all_tasks, N, SEED)
    by_id = {t["id"]: t for t in all_tasks}
    corpus = load_corpus()
    system = load_prompt(tomllib.loads(CFG.read_text())["system_prompt"])

    def first(tid: str) -> list[dict]:
        t = by_id[tid]
        return initial_messages(t, {c: probe(corpus[c]) for c in t["inputs"]}, system)

    rows = [{"name": f"first-turn:{tid}", "messages": first(tid)} for tid in ids[:n]]
    ref = Path("reports/2026-11-22-m3-ckpt60-dev/grpo-m3-ckpt60-q8")
    eps = {
        e["task_id"]: e for e in map(json.loads, (ref / "episodes.jsonl").read_text().splitlines())
    }
    tid = next(i for i in ids if i in eps and len(eps[i]["turns"]) >= 3 and eps[i]["turns"][0]["observation"] == {"spec": "confirmed"})  # fmt: skip
    msgs = first(tid)
    for t in eps[tid]["turns"][
        :2
    ]:  # spec confirmed -> run -> (its observation): the third model turn's prompt
        msgs += [
            {"role": "assistant", "content": t["assistant"]},
            {"role": "user", "content": json.dumps(t["observation"])},
        ]
    rows.append({"name": f"multi-turn:{tid}", "messages": msgs})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1) + "\n")
    print(f"{len(rows)} fixtures -> {out}")


def run(a: argparse.Namespace) -> None:
    from eval.hf_policy import HFPolicy  # torch only when we actually run a model

    dest = a.out / a.name
    if dest.exists():
        raise SystemExit(f"refusing to overwrite {dest}")
    cfg = tomllib.loads(CFG.read_text())
    all_tasks = load_tasks("dev", "dev-eval")  # dev only
    ids = set(sample_ids(all_tasks, N, SEED))
    tasks = [t for t in all_tasks if t["id"] in ids]
    raw = ("".join(json.dumps(t) + "\n" for t in tasks)).encode()
    run_baseline(
        system="M3", policy=HFPolicy(a.model_dir), tasks=tasks, out=dest, corpus=load_corpus(),
        meta={"model": a.name, "quant": cfg["quant"], "temperature": 0.0, "model_config": str(CFG), "system_prompt": cfg["system_prompt"],
              "constrained_decoding": False, "require_spec": True, "stop_after_ask": True, "parity_sample_seed": SEED, "model_dir": str(a.model_dir)},
        tasks_sha256=hashlib.sha256(raw).hexdigest(), system_prompt_text=load_prompt(cfg["system_prompt"]),
        require_spec=True, stop_after_ask=True,
    )  # fmt: skip
    by_id = {t["id"]: t for t in tasks}
    ref, new = side(a.ref_run, by_id, ids), side(dest, by_id, ids)
    if set(ref["res"]) != set(new["res"]) or len(new["res"]) != N:
        raise SystemExit("task sets differ: refusing to compare")
    p = parity(
        {i: bool(r["success"]) for i, r in ref["res"].items()},
        {i: bool(r["success"]) for i, r in new["res"].items()},
    )
    tr, tn = turns(a.ref_run), turns(dest)
    p["first_turn_identical"] = sum(tr[i][:1] == tn[i][:1] for i in ids) / N
    p["transcript_identical"] = sum(tr[i] == tn[i] for i in ids) / N
    summary = {"name": a.name, "ref_run": str(a.ref_run), "parity_ref_a_vs_this_b": p,
               "ref": {k: v for k, v in ref.items() if k not in ("res", "eps")}, "this": {k: v for k, v in new.items() if k not in ("res", "eps")},
               "taxonomy": {"ref": taxonomy(ref["eps"], ref["res"]), a.name: taxonomy(new["eps"], new["res"])}}  # fmt: skip
    for (
        spec
    ) in (
        a.also
    ):  # extra reference runs (e.g. the Q4_K_M run) restricted to the sample, for the taxonomy table only
        label, d = spec.split("=", 1)
        extra = side(Path(d), by_id, ids)
        summary["taxonomy"][label] = taxonomy(extra["eps"], extra["res"])
        summary[f"also_{label}"] = {k: v for k, v in extra.items() if k not in ("res", "eps")}
    (a.out / f"{a.name}.parity.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "taxonomy"}, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fixtures")
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--n", type=int, default=10)
    r = sub.add_parser("run")
    r.add_argument("--model-dir", type=Path, required=True)
    r.add_argument("--name", required=True)
    r.add_argument("--ref-run", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--also", nargs="*", default=[], metavar="LABEL=RUN_DIR")
    a = ap.parse_args()
    fixtures(a.out, a.n) if a.cmd == "fixtures" else run(a)


if __name__ == "__main__":
    main()
