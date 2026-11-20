"""Phase 1 results report (EVALUATION §7; plan T24): systems x test splits with Wilson CIs, the preregistered paired
comparisons with Holm-adjusted p-values, by-family / by-difficulty tables, runs per task and the unnecessary
re-encode rate. Refuses mismatched denominators, missing test-run locks and an existing output directory.
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

from eval import spec_errors
from eval.stats import holm, paired_diff_ci, paired_diff_pvalue, wilson_ci
from training import config
from training.env.validator import uses_stream_copy_only

Runs = dict[str, dict[str, Path]]  # system -> split -> run dir


def pooled(success: dict, system: str, split: str) -> dict[str, bool]:
    """Task -> success for `split`; "a+b" pools the tasks of several splits (ids prefixed so they cannot collide)."""
    parts = split.split("+")
    if len(parts) == 1:
        return success[system][split]
    return {f"{p}:{t}": ok for p in parts for t, ok in success[system][p].items()}


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
        tuple[str, str, str, str]
    ],  # (name, system_a, system_b, split): reports b - a
    out: Path,
    *,
    ledger: Path | None = None,
    checkpoints: dict[str, str] | None = None,
    single_seed: bool = True,
    iid_dedup_ids: frozenset[str] | None = None,
) -> Path:
    """`iid_dedup_ids`: the test-iid tasks whose request is not word-for-word a train request (eval.leakage,
    reports/2026-11-20-leakage-audit). The report then shows test-iid on the FULL split and on this subset side by side;
    Holm and the preregistered comparisons stay on the full split, the dedup differences are descriptive.
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
    raw = {}
    for name, a, b, sp in comparisons:
        d, lo, hi = paired_diff_ci(pooled(success, b, sp), pooled(success, a, sp))
        raw[name] = paired_diff_pvalue(pooled(success, b, sp), pooled(success, a, sp))
        results_json["comparisons"].append(
            {"name": name, "split": sp, "a": a, "b": b, "diff_b_minus_a": d, "ci95": [lo, hi]}
        )
        if (
            dedup and sp == "test-iid"
        ):  # same comparison on the deduplicated subset: descriptive, outside Holm
            sub = lambda m: {t: v for t, v in m.items() if t in iid_dedup_ids}  # noqa: E731
            dd, dlo, dhi = paired_diff_ci(sub(success[b][sp]), sub(success[a][sp]))
            results_json.setdefault("descriptive", []).append(
                {
                    "name": name,
                    "split": "test-iid (dedup)",
                    "diff_b_minus_a": dd,
                    "ci95": [dlo, dhi],
                }
            )
        if "+" in sp:  # descriptive only: never enters Holm
            for part in sp.split("+"):
                dd, dlo, dhi = paired_diff_ci(success[b][part], success[a][part])
                results_json.setdefault("descriptive", []).append(
                    {"name": name, "split": part, "diff_b_minus_a": dd, "ci95": [dlo, dhi]}
                )
    adj = holm(raw) if raw else {}
    lines += ["", "## Preregistered comparisons (b - a, paired bootstrap; Holm-adjusted p across all)", "", "| Comparison | split | diff (pp) [95% CI] | raw p | Holm p |", "|---|---|---|---|---|"]  # fmt: skip
    for c in results_json["comparisons"]:
        c["p_raw"], c["p_holm"] = raw[c["name"]], adj[c["name"]]
        lines.append(
            f"| {c['name']} | {c['split']} | {c['diff_b_minus_a'] * 100:+.1f} [{c['ci95'][0] * 100:+.1f}, {c['ci95'][1] * 100:+.1f}] | {c['p_raw']:.4f} | {c['p_holm']:.4f} |"
        )
    if results_json.get("descriptive"):
        lines += ["", "Descriptive only (not in Holm): pooled comparisons split by component; test-iid comparisons on the deduplicated subset.", "", "| Comparison | split | diff (pp) [95% CI] |", "|---|---|---|"]  # fmt: skip
        lines += [
            f"| {c['name']} | {c['split']} | {c['diff_b_minus_a'] * 100:+.1f} [{c['ci95'][0] * 100:+.1f}, {c['ci95'][1] * 100:+.1f}] |"
            for c in results_json["descriptive"]
        ]
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
