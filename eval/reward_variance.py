"""How much GRPO signal is there once the WHOLE reward is used, not just pass/fail? (owner instruction 20 Nov 2026)

uv run python -m eval.reward_variance sample --tasks <train tasks.jsonl> --policy-config eval/configs/m1-0.6b-q8.toml \
    --k 8 --workers 4 --sample 100 [--openings recovery.jsonl] --out <dir>      # train tasks only; needs llama-server
uv run python -m eval.reward_variance analyse --records <dir>/records.jsonl [<dir2>/records.jsonl ...]
uv run python -m eval.reward_variance dev --run reports/<dir>/M1-0.6b-q8 --tasks data/tasks/dev/v1.jsonl

`sample` re-runs the pass-rate protocol (temperature 1.0, prompt v1, spec first) but keeps every sample's reward terms
(`training.grpo.telemetry.grpo_reward`). The earlier pilots kept only pass/fail, so their transcripts do not exist.
A group = the K samples of one task. A group "has signal" if its TOTAL reward is not constant (what GRPO's advantage
uses); the analysis says which term creates the variance, and how many groups have signal only because of a non-pass term.
"""

import argparse
import json
import random
import shutil
import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from eval.stats import wilson_ci
from training import config
from training.env.loop import Episode, run_episode
from training.env.validator import uses_stream_copy_only
from training.grpo.telemetry import _needless_reencode, grpo_reward, record_for

TERMS = ("pass", "partial", "spec_acc", "efficiency", "clarify", "invalid")
EPS = 1e-12


def episode_record(task: dict, ep: Episode, detail: bool = False) -> dict:
    """One sample's flat reward record plus the re-encode flag (the efficiency term's other input).
    `detail` also keeps what a human needs to judge the sample: request, gold and emitted spec, the run commands.
    """
    rec = record_for(task, ep, grpo_reward(task, ep), task["id"]) | {
        "needless_reencode": _needless_reencode(task, ep)
    }
    if detail:
        runs = [json.loads(t["assistant"]) for t in ep.turns if '"action": "run"' in t["assistant"]]
        rec |= {
            "request": task["request"],
            "gold_spec": task.get("gold_spec"),
            "emitted_spec": ep.emitted_spec,
            "run_args": [r.get("args") for r in runs],
        }
    return rec


def _spread(records: list[dict], term: str, w: dict[str, float]) -> float:
    vals = [r["terms"][term] for r in records]
    return abs(w[term]) * (max(vals) - min(vals))


def group_causes(records: list[dict], weights: dict[str, float] | None = None) -> dict:
    """For one group: does the total vary, which terms vary (weighted range), and why efficiency varies.
    The total is recomputed from the stored terms with `weights` (default: the current config), so records sampled
    under one reward can be re-read under another (e.g. spec_acc weight 0)."""
    w = weights or config.REWARD_WEIGHTS
    totals = [sum(w[t] * r["terms"][t] for t in TERMS) for r in records]
    spreads = {t: _spread(records, t, w) for t in TERMS}
    varying = [t for t in TERMS if spreads[t] > EPS]
    passed = [r for r in records if r["terms"]["pass"] > 0]
    eff_sources = []
    if "efficiency" in varying:
        if len({r["needless_reencode"] for r in passed}) > 1:
            eff_sources.append("re_encode")
        if len({r["runs"] for r in passed if not r["needless_reencode"]}) > 1:
            eff_sources.append("runs")
        if 0 < len(passed) < len(records):
            eff_sources.append("pass_differs")
    return {
        "signal": max(totals) - min(totals) > EPS,
        "pass_varies": 0 < len(passed) < len(records),
        "varying": varying,
        "primary": max(TERMS, key=lambda t: spreads[t]) if varying else None,
        "only": varying[0] if len(varying) == 1 else None,
        "efficiency_sources": eff_sources,
    }


def _rate(rs: list[dict], key: str) -> dict:
    k = sum(bool(r[key]) for r in rs)
    p, lo, hi = wilson_ci(k, len(rs)) if rs else (0.0, 0.0, 0.0)
    return {"n": len(rs), "k": k, "rate": p, "ci95": [lo, hi]}


def analyse(records: list[dict], weights: dict[str, float] | None = None) -> dict:
    by_task: dict[str, list[dict]] = {}
    for r in records:
        by_task.setdefault(r["task_id"], []).append(r)
    causes = [group_causes(g, weights) for g in by_task.values()]
    n = len(causes)

    def share(k: int) -> dict:
        p, lo, hi = wilson_ci(k, n)
        return {"n": k, "share": p, "ci95": [lo, hi]}

    pass_const = [c for c in causes if c["signal"] and not c["pass_varies"]]
    return {
        "groups": n,
        "samples": len(records),
        "signal_total_reward": share(sum(c["signal"] for c in causes)),
        "signal_pass_only_view": share(sum(c["pass_varies"] for c in causes)),
        "signal_without_pass_variance": share(len(pass_const)),
        "term_varies": {t: share(sum(t in c["varying"] for c in causes)) for t in TERMS},
        "primary_term": dict(Counter(c["primary"] for c in causes if c["primary"])),
        "only_term": dict(Counter(c["only"] for c in causes if c["only"])),
        "efficiency_sources": dict(Counter(s for c in causes for s in c["efficiency_sources"])),
        "pass_constant_groups_signal_terms": dict(
            Counter(t for c in pass_const for t in c["varying"])
        ),
        "pass_constant_groups_efficiency_sources": dict(
            Counter(s for c in pass_const for s in c["efficiency_sources"])
        ),
        "mean_runs": sum(r["runs"] for r in records) / len(records),
        "needless_reencode_rate_of_passed": _rate(
            [r for r in records if r["passed"]], "needless_reencode"
        ),
    }


def _is_copy_task(task: dict) -> bool:
    refs = task.get("reference_runs")
    return bool(refs) and uses_stream_copy_only(refs[-1]["args"])


def dev_summary(run_dir: Path, tasks: list[dict]) -> dict:
    """Existing greedy dev run, scored with the real reward: runs per task and the needless re-encode rate."""
    by_id = {t["id"]: t for t in tasks}
    recs = [
        episode_record(by_id[d["task_id"]], Episode(**d))
        for d in map(json.loads, (run_dir / "episodes.jsonl").read_text().splitlines())
    ]
    supported = [r for r in recs if r["supported"]]
    ran = [r for r in supported if r["runs"] > 0]
    copy_ref = [r for r in supported if _is_copy_task(by_id[r["task_id"]])]
    return {
        "tasks": len(recs),
        "supported_tasks": len(supported),
        "mean_runs_supported": sum(r["runs"] for r in supported) / len(supported),
        "mean_runs_supported_that_ran": sum(r["runs"] for r in ran) / len(ran),
        "runs_histogram": dict(sorted(Counter(r["runs"] for r in supported).items())),
        "stream_copy_reference_tasks": len(copy_ref),
        "needless_reencode_of_copy_tasks": _rate(copy_ref, "needless_reencode"),
        "needless_reencode_of_passed_copy_tasks": _rate(
            [r for r in copy_ref if r["passed"]], "needless_reencode"
        ),
        "mean_efficiency_term_supported": sum(r["terms"]["efficiency"] for r in supported)
        / len(supported),
        "mean_reward_total": sum(r["total"] for r in recs) / len(recs),
    }


def sample_records(
    tasks: list[dict],
    policy_factory,
    k: int,
    corpus: dict[str, Path],
    jobs_root: Path,
    workers: int,
    on_task=None,
    done: frozenset[str] = frozenset(),
    detail: bool = False,
    **loop_kwargs,
) -> list[dict]:
    """K full episodes per task (tasks in parallel); every sample's reward record is kept."""

    def one(task: dict) -> dict:
        job = jobs_root / uuid.uuid4().hex
        try:
            ep = run_episode(
                task,
                policy_factory(),
                corpus=corpus,
                job_dir=job,
                max_runs=config.MAX_RUNS_PER_JOB,
                **loop_kwargs,
            )
            return episode_record(task, ep, detail)
        finally:
            shutil.rmtree(job, ignore_errors=True)

    def group(task: dict) -> list[dict]:
        recs = [one(task) for _ in range(k)]
        if on_task:
            on_task(task["id"], recs)
        return recs

    todo = [t for t in tasks if t["id"] not in done]
    with ThreadPoolExecutor(workers) as pool:
        return [r for g in pool.map(group, todo) for r in g]


def _load_records(paths: list[Path]) -> list[dict]:
    return [json.loads(x) for p in paths for x in p.read_text().splitlines() if x.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--tasks", type=Path, nargs="+", required=True, help="one or more train files")
    s.add_argument("--policy-config", type=Path, required=True)
    s.add_argument("--k", type=int, default=config.PASS_RATE_SAMPLES)
    s.add_argument("--workers", type=int, default=1)
    s.add_argument("--sample", type=int)
    s.add_argument("--seed", type=int, default=config.BOOTSTRAP_SEED)
    s.add_argument("--openings", type=Path)
    s.add_argument("--ids-file", type=Path, help="only these task ids (one per line)")
    s.add_argument("--detail", action="store_true", help="keep request, specs and run commands")
    s.add_argument("--out", type=Path, required=True)
    an = sub.add_parser("analyse")
    an.add_argument("--records", type=Path, nargs="+", required=True)
    an.add_argument(
        "--weight", nargs="*", default=[], metavar="TERM=VALUE", help="override a reward weight"
    )
    d = sub.add_parser("dev")
    d.add_argument("--run", type=Path, required=True)
    d.add_argument("--tasks", type=Path, required=True)
    a = ap.parse_args()

    if a.cmd == "analyse":
        w = config.REWARD_WEIGHTS | {k: float(v) for k, v in (x.split("=") for x in a.weight)}
        print(json.dumps(analyse(_load_records(a.records), w), indent=1))
        return
    files = a.tasks if isinstance(a.tasks, list) else [a.tasks]
    tasks = [json.loads(x) for f in files for x in f.read_text().splitlines() if x.strip()]
    if a.cmd == "dev":
        if any(t["split"] != "dev" for t in tasks):
            raise SystemExit("dev summary reads dev tasks only")
        print(json.dumps(dev_summary(a.run, tasks), indent=1))
        return

    from training.corpus.make_synthetic import ensure_corpus
    from training.policies import policy_from_config
    from training.teacher.generate import load_prompt_v1

    if any(t["split"] != "train" for t in tasks):
        raise SystemExit("reward-variance sampling is on train tasks only (RULES 4.5)")
    if a.ids_file:
        keep = set(a.ids_file.read_text().split())
        tasks = [t for t in tasks if t["id"] in keep]
    if a.sample:
        tasks = random.Random(a.seed).sample(sorted(tasks, key=lambda t: t["id"]), a.sample)
    corpus = ensure_corpus(config.CORPUS_DIR, ids={c for t in tasks for c in t["inputs"]})
    policy = policy_from_config(a.policy_config, None)
    policy.temperature = 1.0
    if a.openings:
        from training.taskgen.recovery import OpeningPolicy, openings_for

        rows = [json.loads(x) for x in a.openings.read_text().splitlines()]
        policy = OpeningPolicy(policy, openings_for(tasks, rows))
    a.out.mkdir(parents=True, exist_ok=True)
    f, lock = a.out / "records.jsonl", threading.Lock()
    done = frozenset(r["task_id"] for r in _load_records([f])) if f.exists() else frozenset()

    def on_task(tid: str, recs: list[dict]) -> None:
        with lock, f.open("a") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in recs))

    sample_records(
        tasks,
        lambda: policy,
        a.k,
        corpus,
        config.JOBS_DIR / "rewardvar",
        a.workers,
        on_task=on_task,
        done=done,
        detail=a.detail,
        system_prompt_text=load_prompt_v1(False),
        require_spec=True,
        stop_after_ask=True,
    )
    out = analyse(_load_records([f]))
    (a.out / "analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
