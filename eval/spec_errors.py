"""Material spec error rate (owner decision, 20 Nov 2026, D-043): how often does the spec the user is asked to confirm
contain an error that would mislead them? An eval metric reported for every system on dev and test; NOT a training reward.

An episode counts as erroneous if its emitted spec, compared with the gold spec, is wrong on a MATERIAL field the gold spec
constrains: container, video width/height (resolution), time start/end (time range), lossless, and a video/audio codec (the
gold spec only names a codec when the request asks for one). "Wrong" = different or missing (EXCEPT a missing container:
the gold spec carries a default mp4 container on 277 of 280 dev tasks even when the request names none, so an omission
claims nothing, while a wrong container does); numbers get a tolerance
(2 px for width/height; the gold's own `tolerance_s`, else 0.2 s, for times). Extra true-but-unconstrained fields, tolerances,
family-tag order are NOT errors (the style variance D-043 removed from the reward). One more case: an emitted `lossless: true`
when the executed run re-encoded is a false claim and counts.
Denominator: supported tasks whose gold spec constrains at least one material field. A supported task where the episode
produced no spec counts as an error (failures stay in the denominator). Limitation: a wrong value for a field the gold spec
leaves unconstrained (other than the lossless claim) is not seen.

uv run python -m eval.spec_errors --tasks data/tasks/dev/v1.jsonl M1=reports/<dir>/<run> B0=reports/<dir>/<run>
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from eval.stats import wilson_ci
from training.grpo.telemetry import _flatten

MATERIAL = (
    "container",
    "lossless",
    "video.width",
    "video.height",
    "video.codec",
    "audio.codec",
    "time.start_s",
    "time.end_s",
)
PX_TOL, TIME_TOL_DEFAULT = 2, 0.2


def _gold_fields(gold: dict | None) -> dict[str, object]:
    out = {}
    for key, v in _flatten(gold).items() if gold else []:
        parts = key.split(".", 2)
        if parts[0] == "outputs" and len(parts) == 3 and parts[2] in MATERIAL:
            out[key] = v
    return out


def applicable(task: dict) -> bool:
    flags = task.get("flags") or {}  # schema-required on real tasks; report-test stubs may omit it
    return not (flags.get("ambiguous") or flags.get("unsupported")) and bool(
        _gold_fields(task.get("gold_spec"))
    )


def material_errors(emitted: dict | None, gold: dict | None, re_encoded: bool = False) -> list[str]:
    """Names of the material fields that are wrong (output id stripped); [] if none."""
    g, e = _gold_fields(gold), (_flatten(emitted) if emitted else {})
    flat_gold = _flatten(gold) if gold else {}
    errs = []
    for key, gv in g.items():
        field, ev = key.split(".", 2)[2], e.get(key)
        if ev is None:
            if (
                field != "container"
            ):  # the gold carries a default container on ~99% of tasks: omitting it claims nothing
                errs.append(field)
        elif field in ("video.width", "video.height"):
            if abs(float(ev) - float(gv)) > PX_TOL:
                errs.append(field)
        elif field in ("time.start_s", "time.end_s"):
            tol = float(flat_gold.get(key.rsplit(".", 1)[0] + ".tolerance_s", TIME_TOL_DEFAULT))
            if abs(float(ev) - float(gv)) > tol:
                errs.append(field)
        elif ev != gv:
            errs.append(field)
    claims_lossless = any(k.endswith(".lossless") and v is True for k, v in e.items())
    if claims_lossless and re_encoded and "lossless" not in errs:
        errs.append("lossless_claim_false")
    return errs


def episode_re_encoded(ep: dict) -> bool:
    outs = (ep.get("last_check") or {}).get("outputs", {})
    return any(o.get("measurements", {}).get("re_encoded") for o in outs.values())


def summarize(tasks: dict[str, dict], episodes: dict[str, dict]) -> dict:
    """{n, errors, rate, ci95, by_field} over the applicable tasks that have an episode."""
    n = k = 0
    fields: Counter = Counter()
    for tid, t in tasks.items():
        if not applicable(t) or tid not in episodes:
            continue
        ep = episodes[tid]
        errs = (
            material_errors(ep.get("emitted_spec"), t["gold_spec"], episode_re_encoded(ep))
            if ep.get("emitted_spec")
            else ["no_spec"]
        )
        n += 1
        k += bool(errs)
        fields.update(errs)
    p, lo, hi = wilson_ci(k, n) if n else (0.0, 0.0, 0.0)
    # a system with no spec step at all (the regex baseline, a base model outside the spec-first protocol) is "n/a", not
    # "100% wrong"; a spec-first model that sometimes fails to emit one still counts those episodes as errors
    emits_spec = any(
        episodes[t].get("emitted_spec")
        for t, tk in tasks.items()
        if applicable(tk) and t in episodes
    )
    return {
        "n": n,
        "errors": k,
        "rate": p,
        "ci95": [lo, hi],
        "by_field": dict(fields.most_common()),
        "emits_spec": emits_spec,
    }


def fmt(s: dict) -> str:
    if not s["emits_spec"]:
        return "n/a (emits no spec)"
    return f"{s['errors']}/{s['n']} = {s['rate']:.0%} [{s['ci95'][0]:.0%}, {s['ci95'][1]:.0%}]"


def load_episodes(run_dir: Path) -> dict[str, dict]:
    f = run_dir / "episodes.jsonl"
    return (
        {e["task_id"]: e for e in map(json.loads, f.read_text().splitlines())} if f.exists() else {}
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--tasks", type=Path, required=True, help="dev tasks (test splits go through final_report)"
    )
    ap.add_argument("runs", nargs="+", help="LABEL=run_dir")
    a = ap.parse_args()
    tasks = {t["id"]: t for t in map(json.loads, a.tasks.read_text().splitlines())}
    if any(t["split"] != "dev" for t in tasks.values()):
        raise SystemExit(
            "this CLI reads dev tasks only; test splits are reported by eval.final_report"
        )
    print("| System | material spec error rate | by field |\n|---|---|---|")
    for label, d in (x.split("=", 1) for x in a.runs):
        s = summarize(tasks, load_episodes(Path(d)))
        print(f"| {label} | {fmt(s)} | {s['by_field']} |")


if __name__ == "__main__":
    main()
