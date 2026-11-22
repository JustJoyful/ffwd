"""Human review sheet: 50 random PASSED outputs of one system (A4; EVALUATION §6 "inspect 50 random passed outputs by eye").

uv run python -m eval.passed_review --runs reports/<date>-phase-1-runs/runs/M3-test-iid reports/<date>-phase-1-runs/runs/M3-test-phrasing \
    reports/<date>-phase-1-runs/runs/M3-test-compositional --out reports/<date>-m3-passed-review [--n 50] [--seed 20261115]
(add `--dev` to rehearse on dev runs: tasks come from the dev split instead of the guarded test loader)

The sample is drawn by seed from the sorted ids of the passed episodes of all the given runs, never by content. The sheet
(`review-sheet.csv` for the owner to fill in, `review-sheet.md` to read) shows, per task: the request, what the gold spec
means in plain words, what the model said it would do, the command that produced the output, and the output's measured
properties and path. The question is NOT "did the checker pass" (it did) but "does this output do what the request asks?",
which is how checker blind spots are found. Empty columns `verdict` (ok / problem), `problem`, `notes` are for the reviewer.
Writes nothing else; the media stay in data/jobs (paths in the sheet).
"""

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

from eval.final_report import load
from training import config
from training.env.describe_spec import describe_spec
from training.env.probe import probe
from training.taskgen.loader import load_tasks

COLUMNS = ["n", "task_id", "split", "request", "gold_spec_plain", "model_spec_plain", "command", "runs", "output_properties", "output_path", "verdict", "problem", "notes"]  # fmt: skip


def last_command(ep: dict) -> str:
    for turn in reversed(ep.get("turns", [])):
        try:
            a = json.loads(turn["assistant"])
        except (ValueError, TypeError, KeyError):
            continue
        if isinstance(a, dict) and a.get("action") == "run":
            return "ffmpeg " + " ".join(a.get("args", []))
    return ""


def properties(out_dir: Path) -> tuple[str, str]:
    """(path, human-readable measured properties) of the first output file in the last run's out dir."""
    files = sorted(p for p in out_dir.glob("*") if p.is_file()) if out_dir.exists() else []
    if not files:
        return "", "output file not found (job dir deleted?)"
    p = probe(files[0])
    v = next((s for s in p["streams"] if s["type"] == "video"), None)
    has_audio = any(s["type"] == "audio" for s in p["streams"])
    bits = [f"{p['duration_s']:.2f} s", f"{files[0].stat().st_size / 1e6:.2f} MB", files[0].suffix.lstrip("."), "audio" if has_audio else "no audio"]  # fmt: skip
    if v:
        bits.insert(1, f"{v.get('width')}x{v.get('height')} {v.get('codec')} {v.get('fps')} fps")
    return str(files[0]), "; ".join(bits)


def row(n: int, split: str, task: dict, ep: dict, jobs_dir: Path) -> dict:
    spec = ep.get("emitted_spec")
    path, props = properties(jobs_dir / task["id"] / f"run{ep['runs']}" / "out")
    return {
        "n": n, "task_id": task["id"], "split": split, "request": task["request"],
        "gold_spec_plain": " | ".join(describe_spec(task["gold_spec"])) if task["gold_spec"] else "(no gold spec)",
        "model_spec_plain": " | ".join(describe_spec(spec)) if spec else "(none)",
        "command": last_command(ep), "runs": ep["runs"], "output_properties": props, "output_path": path,
        "verdict": "", "problem": "", "notes": "",
    }  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=config.BOOTSTRAP_SEED)
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--jobs-root", type=Path, default=config.JOBS_DIR)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    pool = []  # (split, run dir, task id) of every passed episode
    tasks: dict[str, dict] = {}
    for d in a.runs:
        split = "dev" if a.dev else d.name.split("-", 1)[1]
        tasks[split] = tasks.get(split) or {t["id"]: t for t in load_tasks(split, "dev-eval" if a.dev else "test-eval")}  # fmt: skip
        res, _ = load(d)
        pool += [(split, d, t) for t, r in sorted(res.items()) if r["success"]]
    if len(pool) < a.n:
        raise SystemExit(f"only {len(pool)} passed episodes, need {a.n}")
    picked = random.Random(a.seed).sample(pool, a.n)
    rows = []
    for i, (split, d, tid) in enumerate(picked, 1):
        _, eps = load(d)
        rows.append(row(i, split, tasks[split][tid], eps[tid], a.jobs_root / d.name))
    a.out.mkdir(parents=True)
    with (a.out / "review-sheet.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, COLUMNS)
        w.writeheader()
        w.writerows(rows)
    md = ["# Review sheet: 50 random passed outputs", "", "For each: does the output do what the **request** asks? Fill `verdict` (ok / problem), `problem` (what is wrong) and `notes` in `review-sheet.csv`.", ""]  # fmt: skip
    for r in rows:
        md += [f"## {r['n']}. `{r['task_id']}` ({r['split']})", f"**Request:** {r['request']}", f"**Gold spec means:** {r['gold_spec_plain']}", f"**Model said:** {r['model_spec_plain']}", f"**Command ({r['runs']} run(s)):** `{r['command']}`", f"**Output:** {r['output_properties']}  ", f"`{r['output_path']}`", ""]  # fmt: skip
    (a.out / "review-sheet.md").write_text("\n".join(md) + "\n")
    manifest = {"seed": a.seed, "n": a.n, "pool_size": len(pool), "runs": {str(d): hashlib.sha256((d / "results.jsonl").read_bytes()).hexdigest() for d in a.runs}, "picked": [[r["split"], r["task_id"]] for r in rows], "dev_rehearsal": a.dev}  # fmt: skip
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"wrote {a.out} ({a.n} of {len(pool)} passed episodes)")


if __name__ == "__main__":
    main()
