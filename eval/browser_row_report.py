"""Report for the browser row of Phase 1 (Amendment 4): M3 Q5_K_M in the browser (wllama) next to M3 Q8_0, descriptive only.

    uv run python -m eval.browser_row_report --browser-root reports/<date>-phase-1-browser-row --out reports/<date>-phase-1-browser-row/report

Fixed by Amendment 4 before the run: primary = paired success difference (browser minus M3 Q8_0) on the three generated
splits pooled (paired bootstrap, 10,000 resamples, seed 20261115, `eval.stats.paired_diff_ci`); guard = the one-sided
97.5% lower bound of that difference above -2.0 pp, reported as shown / not shown; NO p-values and NO efficiency claim.
Everything else is descriptive. It reuses the Phase 1 loaders and statistics and does not touch the Phase 1 report.
"""

import argparse
import json
import subprocess
from pathlib import Path

from eval import spec_errors
from eval.browser_parity import turn_stats
from eval.final_report import load, metric_values
from eval.stats import paired_diff_ci, wilson_ci
from training import config
from training.taskgen.loader import load_tasks

BROWSER, BASE = "M3-browser", "M3"  # base = M3 Q8_0, the Phase 1 headline
CONTEXT = ("M1", "X1")  # context only
SPLITS = ("test-iid", "test-phrasing", "test-compositional")
PHASE1_RUNS = config.REPO_ROOT / "reports" / "2026-11-22-phase1-runs" / "runs"
GUARD_MARGIN = config.PREREG_GUARD_MARGIN  # 0.02: Amendment 3 item 5, reused unchanged


def _success(res: dict) -> dict[str, float]:
    return {t: float(r["success"]) for t, r in res.items()}


def _pool(per_split: dict[str, dict[str, float]], splits) -> dict[str, float]:
    return {f"{sp}:{t}": v for sp in splits for t, v in per_split[sp].items()}


def _diff(b: dict, a: dict) -> dict:
    d, lo, hi = paired_diff_ci(b, a)  # b - a; (2.5th, 97.5th) percentiles
    return {"n": len(a), "diff": d, "ci95": [lo, hi]}


def analyse(
    loaded: dict[str, dict[str, tuple[dict, dict]]],
    tasks_by_split: dict[str, dict[str, dict]],
    latency: dict[str, dict] | None = None,
) -> dict:
    """`loaded[system][split] = (results, episodes)`. Task sets must match the split exactly (a missing task is a denominator bug)."""
    for s, by in loaded.items():
        for sp, (res, _) in by.items():
            if set(res) != set(tasks_by_split[sp]):
                raise ValueError(f"{s} on {sp}: results do not cover exactly the split's tasks")
    splits = [sp for sp in SPLITS if sp in loaded[BROWSER]]
    succ = {s: {sp: _success(loaded[s][sp][0]) for sp in by} for s, by in loaded.items()}
    out: dict = {
        "splits": splits,
        "systems": {},
        "note": "descriptive extra row (Amendment 4); no p-values, no efficiency claim",
    }
    for s in succ:
        row = {}
        for sp in succ[s]:
            k, n = int(sum(succ[s][sp].values())), len(succ[s][sp])
            p, lo, hi = wilson_ci(k, n)
            row[sp] = {"k": k, "n": n, "rate": p, "ci95": [lo, hi]}
        out["systems"][s] = row
    # primary + guard
    prim = _diff(_pool(succ[BROWSER], splits), _pool(succ[BASE], splits))
    prim["guard"] = {
        "margin": GUARD_MARGIN,
        "lower_bound_975": prim["ci95"][0],
        "shown": prim["ci95"][0] > -GUARD_MARGIN,
    }
    out["primary"] = prim
    out["per_split"] = {sp: _diff(succ[BROWSER][sp], succ[BASE][sp]) for sp in splits}
    out["context_only"] = {}
    for other in CONTEXT:
        have = [sp for sp in splits if sp in loaded.get(other, {})]
        if have:
            out["context_only"][other] = {
                "splits": have,
                **_diff(_pool(succ[BROWSER], have), _pool(succ[other], have)),
            }
    # needless-re-encode-or-fail on copy-eligible tasks, pooled over iid + phrasing (the Q3a definition); lower is better
    q3 = [sp for sp in ("test-iid", "test-phrasing") if sp in splits]
    nof = {s: _pool({sp: metric_values("needless_or_fail", tasks_by_split[sp], *loaded[s][sp]) for sp in q3}, q3) for s in (BROWSER, BASE)}  # fmt: skip
    if nof[BASE]:
        out["needless_or_fail"] = {"splits": q3, "n": len(nof[BASE]), "browser": sum(nof[BROWSER].values()) / len(nof[BROWSER]),
                                   "base": sum(nof[BASE].values()) / len(nof[BASE]), "diff_browser_minus_base": _diff(nof[BROWSER], nof[BASE])}  # fmt: skip
    # invalid-action episodes, context-rule endings, other infrastructure errors, spec error rate
    rows = {sp: list(loaded[BROWSER][sp][0].values()) for sp in splits}
    out["invalid_action_episodes"] = {s: {sp: sum(r["invalid_turns"] > 0 for r in loaded[s][sp][0].values()) for sp in by} for s, by in loaded.items()}  # fmt: skip
    out["context_rule_endings"] = {
        sp: sum(str(r.get("error", "")).startswith("ContextFull") for r in rs)
        for sp, rs in rows.items()
    }
    out["other_errors"] = {sp: [{"task_id": r["task_id"], "error": r["error"]} for r in rs if r.get("end_reason") == "error" and not str(r.get("error", "")).startswith("ContextFull")] for sp, rs in rows.items()}  # fmt: skip
    out["material_spec_errors"] = {s: {sp: spec_errors.summarize(tasks_by_split[sp], loaded[s][sp][1]) for sp in by} for s, by in loaded.items() if s in (BROWSER, BASE)}  # fmt: skip
    if latency:
        out["latency"] = latency
    return out


def render(r: dict) -> str:
    pct = lambda x: f"{100 * x:+.2f} pp"  # noqa: E731
    ci = lambda d: f"[{100 * d['ci95'][0]:+.2f}, {100 * d['ci95'][1]:+.2f}]"  # noqa: E731
    L = ["# Phase 1 browser row (Amendment 4): M3 Q5_K_M in the browser (wllama), extra row, descriptive", "",
         "M3 Q8_0 stays the headline model. No p-values and no efficiency claim are made for this row. Failed, errored and context-ended episodes count as failures.", "",  # fmt: skip
         "| System | " + " | ".join(r["splits"]) + " |", "|---|" + "---|" * len(r["splits"])]  # fmt: skip
    for s, row in r["systems"].items():
        L.append(f"| {s} | " + " | ".join(f"{row[sp]['k']}/{row[sp]['n']} = {row[sp]['rate']:.1%} [{row[sp]['ci95'][0]:.1%}, {row[sp]['ci95'][1]:.1%}]" if sp in row else "-" for sp in r["splits"]) + " |")  # fmt: skip
    p = r["primary"]
    g = p["guard"]
    L += ["", "## Primary (descriptive) and guard", "",
          f"Paired success difference {BROWSER} minus {BASE}, three splits pooled (n = {p['n']}): **{pct(p['diff'])}** (95% CI {ci(p)} pp).",  # fmt: skip
          f"Guard (Amendment 3 item 5 reused): one-sided 97.5% lower bound {pct(g['lower_bound_975'])} against -{100 * g['margin']:.1f} pp: **{'shown' if g['shown'] else 'NOT shown'}**.", "",  # fmt: skip
          "| Split | n | diff | 95% CI (pp) |", "|---|---|---|---|"]  # fmt: skip
    L += [f"| {sp} | {d['n']} | {pct(d['diff'])} | {ci(d)} |" for sp, d in r["per_split"].items()]
    L += ["", "## Context only (not part of any claim)", ""]
    L += [
        f"- {BROWSER} minus {o} on {', '.join(d['splits'])}: {pct(d['diff'])} {ci(d)} pp (n = {d['n']})"
        for o, d in r["context_only"].items()
    ]
    if "needless_or_fail" in r:
        n = r["needless_or_fail"]
        L += ["", f"Needless-re-encode-or-fail on copy-eligible tasks ({', '.join(n['splits'])}, n = {n['n']}; lower is better): browser {n['browser']:.1%}, {BASE} {n['base']:.1%}, difference {pct(n['diff_browser_minus_base']['diff'])} {ci(n['diff_browser_minus_base'])}."]  # fmt: skip
    L += ["", "## Episodes that did not complete normally", "",
          "Invalid-action episodes: " + "; ".join(f"{s} {sum(v.values())}" for s, v in r["invalid_action_episodes"].items()) + ".",
          "Ended by the context rule (prompt + 512-token reply budget would not fit in n_ctx 8192, counted as not done): " + ", ".join(f"{sp} {n}" for sp, n in r["context_rule_endings"].items()) + ".",  # fmt: skip
          "Other infrastructure errors (counted as failures): " + ", ".join(f"{sp} {len(v)}" for sp, v in r["other_errors"].items()) + "."]  # fmt: skip
    L += ["", "## Material spec error rate (descriptive; lower is better)", ""]
    for s, by in r["material_spec_errors"].items():
        L.append(f"- {s}: " + "; ".join(f"{sp} {spec_errors.fmt(v)}" for sp, v in by.items()))
    if "latency" in r:
        L += ["", "## Latency (bridge log; one laptop, nothing else heavy running)", "", "| Split | turns | median | p90 | max | prompt tok/s | generation tok/s |", "|---|---|---|---|---|---|---|"]  # fmt: skip
        for sp, t in r["latency"].items():
            w = t["wall_ms"]
            L.append(f"| {sp} | {t['turns']} | {w['median'] / 1000:.2f} s | {w['p90'] / 1000:.2f} s | {w['max'] / 1000:.1f} s | {t['prompt_tok_s']:.0f} | {t['gen_tok_s']:.1f} |")  # fmt: skip
    L += ["", "One laptop (RTX 3050 6 GB), one Chromium build, one seed: this row describes that configuration, not the field. Its runtime build (wllama's llama.cpp) differs from the native one used for the other rows."]  # fmt: skip
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    tasks_by_split = {sp: {t["id"]: t for t in load_tasks(sp, "test-eval")} for sp in SPLITS}
    loaded = {BROWSER: {sp: load(a.browser_root / "runs" / f"{BROWSER}-{sp}") for sp in SPLITS}}
    for s in (BASE, *CONTEXT):
        loaded[s] = {sp: load(d) for sp in SPLITS if (d := PHASE1_RUNS / f"{s}-{sp}").exists()}
    latency = {
        sp: turn_stats(a.browser_root / "bridges" / f"{BROWSER}-{sp}" / "turns.jsonl")
        for sp in SPLITS
    }
    res = analyse(loaded, tasks_by_split, latency)
    a.out.mkdir(parents=True)
    (a.out / "results.json").write_text(json.dumps(res, indent=2) + "\n")
    (a.out / "summary.md").write_text(render(res))
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=config.REPO_ROOT
    ).stdout.strip()
    runs = {
        sp: json.loads((a.browser_root / "runs" / f"{BROWSER}-{sp}" / "manifest.json").read_text())
        for sp in SPLITS
    }
    (a.out / "manifest.json").write_text(json.dumps({"report_commit": commit, "bootstrap": {"resamples": config.BOOTSTRAP_RESAMPLES, "seed": config.BOOTSTRAP_SEED},
                                                     "runs": {sp: {k: m.get(k) for k in ("checkpoint", "ffwd_commit", "ffwd_web_commit", "nvidia", "kernel", "tasks_sha256", "n_tasks", "started", "finished")} for sp, m in runs.items()}}, indent=2) + "\n")  # fmt: skip
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
