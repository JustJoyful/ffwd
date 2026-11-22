"""Phase 1 results report (EVALUATION §7; plan T24): systems x test splits with Wilson CIs, the preregistered paired
comparisons as a fixed-sequence procedure (Amendment 3) with the success guard, by-family / by-difficulty tables, runs
per task and the unnecessary re-encode rate. Refuses mismatched denominators, missing test-run locks and an existing
output directory.
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

from eval import spec_errors
from eval.copy_eligible_counts import copy_eligible, graded
from eval.stats import paired_diff_ci, paired_diff_pvalue, wilson_ci
from training import config
from training.env.validator import uses_stream_copy_only

Runs = dict[str, dict[str, Path]]  # system -> split -> run dir


def normalise(c: tuple) -> tuple:
    """(name, a, b, split) -> (name, a, b, split, "success", False); 6-tuples pass through."""
    return c if len(c) == 6 else (*c, "success", False)


def needless_or_fail(result: dict, ep: dict | None) -> float:
    """Q3a outcome on a copy-eligible task: 1 if the episode failed, ran nothing, or its final check reports
    `re_encoded` (the definition of training.grpo.telemetry._needless_reencode); else 0. Failures stay in.
    """
    if not result["success"] or result["runs"] == 0:
        return 1.0
    check = (ep or {}).get("last_check")
    if (
        not check
    ):  # a passed episode without a check record cannot be classified: refuse, do not guess
        raise ValueError(f"{result['task_id']}: passed but has no last_check in episodes.jsonl")
    outs = check.get("outputs", {})
    return float(any(o.get("measurements", {}).get("re_encoded") for o in outs.values()))


def metric_values(
    metric: str, tasks: dict[str, dict], results: dict[str, dict], eps: dict[str, dict]
) -> dict[str, float]:
    """Task -> value for one preregistered metric. `success`: every task. `runs`: graded tasks (not ambiguous, not
    unsupported), runs used, 0 if none. `needless_or_fail`: copy-eligible tasks only (a property of the task file).
    """
    if metric == "success":
        return {t: float(r["success"]) for t, r in results.items()}
    if metric == "runs":
        return {t: float(results[t]["runs"]) for t in tasks if graded(tasks[t])}
    if metric == "needless_or_fail":
        return {
            t: needless_or_fail(results[t], eps.get(t)) for t in tasks if copy_eligible(tasks[t])
        }
    raise ValueError(f"unknown metric {metric!r}")


def load(run_dir: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    results = {
        r["task_id"]: r
        for r in map(json.loads, (run_dir / "results.jsonl").read_text().splitlines())
    }
    eps = {}
    if (run_dir / "episodes.jsonl").exists():
        eps = {
            e["task_id"]: e
            for e in map(json.loads, (run_dir / "episodes.jsonl").read_text().splitlines())
        }
    return results, eps


def last_run_args(ep: dict) -> list[str] | None:
    for turn in reversed(ep.get("turns", [])):
        try:
            action = json.loads(turn["assistant"])
        except (ValueError, TypeError):
            continue
        if isinstance(action, dict) and action.get("action") == "run":
            return action.get("args")
    return None


def reencode_rate(results: dict, eps: dict, tasks: dict[str, dict]) -> float | None:
    """Among tasks that HAVE a lossless (stream-copy) reference solution, the share where the model re-encoded."""
    lossless = [
        tid
        for tid, t in tasks.items()
        if t.get("reference_runs") and uses_stream_copy_only(t["reference_runs"][-1]["args"])
    ]
    scored = [(tid, last_run_args(eps[tid])) for tid in lossless if tid in eps]
    scored = [(tid, a) for tid, a in scored if a is not None]
    return sum(not uses_stream_copy_only(a) for _, a in scored) / len(scored) if scored else None


def final_report(
    runs: Runs,
    tasks_by_split: dict[str, dict[str, dict]],
    comparisons: list[
        tuple
    ],  # config.PREREG_COMPARISONS order; (name, a, b, split[, metric, lower]): reports b - a
    out: Path,
    *,
    ledger: Path | None = None,
    checkpoints: dict[str, str] | None = None,
    single_seed: bool = True,
    iid_dedup_ids: frozenset[str] | None = None,
) -> Path:
    """`iid_dedup_ids`: the test-iid tasks whose request is not word-for-word a train request (eval.leakage,
    reports/2026-11-20-leakage-audit). The report then shows test-iid on the FULL split and on this subset side by side;
    The preregistered sequence stays on the full split, the dedup differences are descriptive.
    """
    if out.exists():
        raise FileExistsError(out)
    loaded: dict[str, dict[str, tuple[dict, dict]]] = {
        s: {sp: load(d) for sp, d in by.items()} for s, by in runs.items()
    }
    for split in {sp for by in runs.values() for sp in by}:
        ids = {s: set(loaded[s][split][0]) for s in runs if split in runs[s]}
        if len({frozenset(v) for v in ids.values()}) > 1:
            raise ValueError(
                f"systems have different task sets on {split}: a missing task is a denominator bug"
            )
        if set(tasks_by_split[split]) != next(iter(ids.values())):
            raise ValueError(f"results on {split} do not cover exactly the split's tasks")
    if ledger is not None:
        done = {
            (r["system"], r["checkpoint"], r["split"])
            for r in map(json.loads, ledger.read_text().splitlines())
        }
        for s, by in runs.items():
            for sp in by:
                if sp in config.TEST_SPLITS and (s, (checkpoints or {}).get(s, ""), sp) not in done:
                    raise ValueError(
                        f"no test-run lock entry for {s} on {sp}: it was not run through eval/testlock.py"
                    )
    success = {
        s: {sp: {t: bool(r["success"]) for t, r in loaded[s][sp][0].items()} for sp in by}
        for s, by in runs.items()
    }
    splits = sorted({sp for by in runs.values() for sp in by})
    dedup = "test-iid" in splits and iid_dedup_ids is not None
    if dedup and not iid_dedup_ids <= set(tasks_by_split["test-iid"]):
        raise ValueError("iid_dedup_ids names tasks that are not in test-iid")
    cols = splits + (["test-iid (dedup)"] if dedup else [])
    lines = ["# Phase 1 results", "", "Wilson 95% CIs; failed, timed-out, malformed and errored episodes count as failures.", "",
             "| System | " + " | ".join(cols) + " | runs/task (iid) | re-encode rate |", "|---|" + "---|" * (len(cols) + 2)]  # fmt: skip
    results_json: dict = {"systems": {}, "comparisons": []}
    for s in runs:
        cells, entry = [], {}
        for sp in splits:
            if sp not in success[s]:
                cells.append("-")
                continue
            k, n = sum(success[s][sp].values()), len(success[s][sp])
            p, lo, hi = wilson_ci(k, n)
            cells.append(f"{k}/{n} = {p:.0%} [{lo:.0%}, {hi:.0%}]")
            entry[sp] = {"k": k, "n": n, "rate": p, "ci95": [lo, hi]}
        if dedup:
            sub = [ok for t, ok in success[s]["test-iid"].items() if t in iid_dedup_ids]
            k, n = sum(sub), len(sub)
            p, lo, hi = wilson_ci(k, n)
            cells.append(f"{k}/{n} = {p:.0%} [{lo:.0%}, {hi:.0%}]")
            entry["test-iid (dedup)"] = {"k": k, "n": n, "rate": p, "ci95": [lo, hi]}
        iid = loaded[s].get("test-iid")
        rpt = (sum(r["runs"] for r in iid[0].values()) / len(iid[0])) if iid else None
        rer = reencode_rate(*iid, tasks_by_split["test-iid"]) if iid else None
        entry |= {"runs_per_task_iid": rpt, "reencode_rate_iid": rer}
        results_json["systems"][s] = entry
        lines.append(
            f"| {s} | "
            + " | ".join(cells)
            + f" | {rpt:.2f} | {('%.0f%%' % (100 * rer)) if rer is not None else 'n/a'} |"
            if rpt is not None
            else f"| {s} | " + " | ".join(cells) + " | - | - |"
        )
    # material spec error rate (eval.spec_errors, D-043): descriptive, outside the preregistered family, lower is better
    lines += ["", "## Material spec error rate (container, resolution, time range, lossless, requested codec; lower is better)", "",
              "| System | " + " | ".join(splits) + " |", "|---|" + "---|" * len(splits)]  # fmt: skip
    results_json["material_spec_errors"] = {}
    for s in runs:
        row = {
            sp: spec_errors.summarize(tasks_by_split[sp], loaded[s][sp][1])
            for sp in splits
            if sp in loaded[s]
        }
        results_json["material_spec_errors"][s] = row
        lines.append(
            f"| {s} | "
            + " | ".join(spec_errors.fmt(row[sp]) if sp in row else "-" for sp in splits)
            + " |"
        )

    def vals(metric: str, system: str, split: str) -> dict[str, float]:
        """Per-task values of `metric` for `split`; "a+b" pools the tasks of several splits (ids prefixed)."""
        parts = split.split("+")
        out = {}
        for p in parts:
            res, eps = loaded[system][p]
            for t, v in metric_values(metric, tasks_by_split[p], res, eps).items():
                out[t if len(parts) == 1 else f"{p}:{t}"] = v
        return out

    # Fixed-sequence procedure (Amendment 3): test in the given order, each step at alpha only if every earlier step
    # rejected in its FAVOURABLE direction; after the first step that did not, the rest are descriptive (no p claimed).
    sub = lambda m: {t: v for t, v in m.items() if t in iid_dedup_ids}  # noqa: E731
    alive = True
    for name, a, b, sp, metric, lower in map(normalise, comparisons):
        va, vb = vals(metric, a, sp), vals(metric, b, sp)
        if (
            not va
        ):  # e.g. no copy-eligible task in a partial or dry run: nothing to test, so the sequence stops here
            results_json["comparisons"].append(
                {"name": name, "split": sp, "a": a, "b": b, "metric": metric, "lower_is_better": lower, "n": 0,
                 "diff_b_minus_a": None, "ci95": None, "favourable": False, "p_raw": None,
                 "status": "NOT computable (no tasks): sequence stops" if alive else "descriptive (after the stop)"}
            )  # fmt: skip
            alive = False
            continue
        d, lo, hi = paired_diff_ci(vb, va)  # b - a
        p = paired_diff_pvalue(vb, va)
        favourable = d < 0 if lower else d > 0
        if alive:
            sig = p < config.PREREG_ALPHA
            ok = sig and favourable
            status = "rejected" if ok else ("significant, UNFAVOURABLE: sequence stops" if sig else "NOT rejected: sequence stops")  # fmt: skip
            alive = ok
        else:
            status = "descriptive (after the stop)"
        results_json["comparisons"].append(
            {"name": name, "split": sp, "a": a, "b": b, "metric": metric, "lower_is_better": lower,
             "n": len(va), "diff_b_minus_a": d, "ci95": [lo, hi], "favourable": favourable,
             "p_raw": None if status.startswith("descriptive") else p, "status": status}
        )  # fmt: skip
        desc = results_json.setdefault("descriptive", [])
        if (
            dedup and sp == "test-iid"
        ):  # the same comparison on the deduplicated subset: descriptive
            dd, dlo, dhi = paired_diff_ci(sub(vb), sub(va))
            desc.append({"name": name, "split": "test-iid (dedup)", "diff_b_minus_a": dd, "ci95": [dlo, dhi]})  # fmt: skip
        if "+" in sp:  # components of a pooled comparison
            for part in sp.split("+"):
                dd, dlo, dhi = paired_diff_ci(vals(metric, b, part), vals(metric, a, part))
                desc.append({"name": name, "split": part, "diff_b_minus_a": dd, "ci95": [dlo, dhi]})  # fmt: skip
    # guard: one-sided 97.5% lower bound of the success difference (percentile 2.5 of the bootstrap) above -margin
    ga, gb, gsplits = config.PREREG_GUARD
    guard = None
    if {ga, gb} <= set(runs) and all(sp in runs[s] for s in (ga, gb) for sp in gsplits):
        gd, glo, _ = paired_diff_ci(vals("success", gb, "+".join(gsplits)), vals("success", ga, "+".join(gsplits)))  # fmt: skip
        guard = {"a": ga, "b": gb, "splits": list(gsplits), "diff_b_minus_a": gd, "lower_bound_975": glo,
                 "margin": config.PREREG_GUARD_MARGIN, "met": glo > -config.PREREG_GUARD_MARGIN}  # fmt: skip
    results_json["guard"] = guard
    eff = [c for c in results_json["comparisons"] if c["metric"] != "success"]
    results_json["efficiency_claim"] = bool(
        guard and guard["met"] and any(c["status"] == "rejected" for c in eff)
    )
    lines += ["", f"## Preregistered comparisons ({config.PREREG_PROCEDURE}, alpha {config.PREREG_ALPHA}; b - a, paired bootstrap; lower is better for runs and needless-or-fail)", "", "| Comparison | split | n | diff [95% CI] | raw p | status |", "|---|---|---|---|---|---|"]  # fmt: skip
    for c in results_json["comparisons"]:
        if c["n"] == 0:
            lines.append(f"| {c['name']} | {c['split']} | 0 | - | - | {c['status']} |")
            continue
        k = 1 if c["metric"] == "runs" else 100  # runs in runs, rates in pp
        u = "" if c["metric"] == "runs" else " pp"
        p = "-" if c["p_raw"] is None else f"{c['p_raw']:.4f}"
        lines.append(
            f"| {c['name']} | {c['split']} | {c['n']} | {c['diff_b_minus_a'] * k:+.3f}{u} [{c['ci95'][0] * k:+.3f}, {c['ci95'][1] * k:+.3f}] | {p} | {c['status']} |"
        )
    if guard:
        lines += ["", f"Guard ({guard['b']} - {guard['a']} success, {'+'.join(guard['splits'])}): {guard['diff_b_minus_a'] * 100:+.2f} pp, one-sided 97.5% lower bound {guard['lower_bound_975'] * 100:+.2f} pp against -{guard['margin'] * 100:.1f} pp: **{'met' if guard['met'] else 'NOT met'}**. Efficiency claim: **{'yes' if results_json['efficiency_claim'] else 'no'}** (needs Q3b or Q3a rejected AND the guard met)."]  # fmt: skip
    else:
        lines += ["", "Guard: not computed (a guard system or split is missing from this run)."]
    if results_json.get("descriptive"):
        lines += ["", "Descriptive only (outside the sequence): pooled comparisons split by component; test-iid comparisons on the deduplicated subset (pp for rates, runs for Q3b).", "", "| Comparison | split | diff [95% CI] |", "|---|---|---|"]  # fmt: skip
        for c in results_json["descriptive"]:
            k = 1 if "runs" in c["name"] else 100
            lines.append(
                f"| {c['name']} | {c['split']} | {c['diff_b_minus_a'] * k:+.3f} [{c['ci95'][0] * k:+.3f}, {c['ci95'][1] * k:+.3f}] |"
            )
    groups: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    for s in runs:
        for sp, by_task in success[s].items():
            for tid, ok in by_task.items():
                t = tasks_by_split[sp][tid]
                family = "family:" + ("+".join(t["families"]) if t["families"] else "unsupported")
                for key in (family, f"difficulty:{t['difficulty']}"):
                    groups[(s, sp, key)][0] += ok
                    groups[(s, sp, key)][1] += 1
    out.mkdir(parents=True)
    with (out / "by_family.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["system", "split", "group", "successes", "n"])
        for (s, sp, key), v in sorted(groups.items()):
            w.writerow([s, sp, key, *v])
    lines += [
        "",
        (
            "Single training seed: differences between M-systems reflect one run each."
            if single_seed
            else ""
        ),
        "",
        "See `by_family.csv` for per-family and per-difficulty results.",
    ]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    (out / "results.json").write_text(json.dumps(results_json, indent=1) + "\n")
    return out
