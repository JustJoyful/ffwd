"""Bulk-run report (milestone "bulk done"): kept-rate overall and per family, cost, cache-hit, family distribution,
and unsupported/ambiguous examples per category AFTER filtering. Reads only the work dir of one run.

uv run python -m training.teacher.report --name bulk-20261119 --out reports/<date>-teacher-bulk
"""

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from eval.stats import wilson_ci
from training import config
from training.taskgen.loader import load_tasks
from training.taskgen.special import ambiguous_intent, nearest_ok, unsupported_intent
from training.teacher.budget import BudgetGuard
from training.teacher.generate import nearest_in_messages


def _pct(k: int, n: int) -> str:
    if not n:
        return "-"
    r, lo, hi = wilson_ci(k, n)
    return f"{k}/{n} = {r:.1%} [{lo:.1%}, {hi:.1%}]"


def analyse(rows: list[dict], tasks: list[dict]) -> dict:
    by_id = {t["id"]: t for t in tasks}
    fam, single, size, unsup, amb, labels = (Counter() for _ in range(6))
    tot = Counter()
    for r in rows:
        t = by_id[r["task_id"]]
        keys = t["families"] or ["ambiguous" if t["flags"]["ambiguous"] else "unsupported"]
        ok = not t["flags"]["unsupported"] or nearest_ok(t, nearest_in_messages(r["messages"]))
        kept = r["passed"] and ok
        for c, ks in ((fam, keys), (single, keys if len(keys) == 1 else [])):
            for k in ks:
                c[(k, "n")] += 1
                c[(k, "passed")] += r["passed"]
                c[(k, "kept")] += kept
        size[(len(t["families"]), "n")] += 1
        size[(len(t["families"]), "kept")] += kept
        tot.update(
            n=1,
            passed=r["passed"],
            kept=kept,
            invalid_traj=r["invalid_turns"] > 0,
            invalid_turns=r["invalid_turns"],
        )
        if t["flags"]["unsupported"]:
            i = unsupported_intent(t)
            unsup[(i, "n")] += 1
            unsup[(i, "passed")] += r["passed"]
            unsup[(i, "kept")] += kept
            if r["passed"]:
                labels[(i, nearest_in_messages(r["messages"]), ok)] += 1
        if t["flags"]["ambiguous"]:
            i = ambiguous_intent(t)
            amb[(i, "n")] += 1
            amb[(i, "kept")] += kept
    return {
        "total": dict(tot),
        "family": fam,
        "single": single,
        "size": size,
        "unsupported": unsup,
        "ambiguous": amb,
        "labels": labels,
    }


def _table(c: Counter, cols: tuple[str, ...], first: str) -> list[str]:
    keys = sorted({k[0] for k in c}, key=lambda k: (len(str(k)), str(k)))
    out = [f"| {first} | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for k in keys:
        out.append(
            f"| {k} | "
            + " | ".join(
                _pct(c[(k, col)], c[(k, "n")]) if col != "n" else str(c[(k, "n")]) for col in cols
            )
            + " |"
        )
    return out


def report(work: Path, tasks: list[dict], out: Path) -> str:
    rows = [json.loads(x) for x in (work / "trajectories.jsonl").read_text().splitlines()]
    a = analyse(rows, tasks)
    t = a["total"]
    chunks = (
        [json.loads(x) for x in (work / "chunks.jsonl").read_text().splitlines()]
        if (work / "chunks.jsonl").exists()
        else []
    )
    guard = BudgetGuard(config.LEDGER_PATH, config.BUDGET_LIFETIME_USD, 1.0, work.name)
    cost, cache = guard.spent(run_only=True), guard.cache_hit_ratio()
    end = (
        json.loads((work / "END.json").read_text())
        if (work / "END.json").exists()
        else {"why": "running"}
    )
    lines = [
        f"# Teacher bulk run `{work.name}` ({datetime.now(UTC):%d %b %Y})", "",
        f"Ended: **{end['why']}**. {t['n']} episodes on train tasks (of {len(tasks)}), DeepSeek `{config.DEEPSEEK_MODEL_ID}` "
        f"({config.DEEPSEEK_MODEL_VERSION_SEEN}), prompt v1 sha256 `{config.SYSTEM_PROMPT_V1_SHA256[:12]}...`, thinking off.", "",
        "| measure | result | gate |", "|---|---|---|",
        f"| kept-rate (checker verdict) | {_pct(t['passed'], t['n'])} | >= {config.TEACHER_KEPT_GATE:.0%} per chunk of {config.TEACHER_CHUNK} |",
        f"| kept after the label filter (SFT input) | {_pct(t['kept'], t['n'])} | |",
        f"| cost (billed at peak rates) | ${cost:.4f} (${cost / max(t['n'], 1):.5f}/episode) | cap $2.30 |",
        f"| cache-hit ratio | {cache:.1%} | >= 60% |",
        f"| trajectories with an invalid-action turn | {_pct(t.get('invalid_traj', 0), t['n'])} ({t.get('invalid_turns', 0)} turns, dropped by the SFT builder) | |", "",
        "## Chunks", "", "| chunk | episodes | kept-rate | label-rejected | chunk $ | running $ | cache-hit | stopped |", "|---|---|---|---|---|---|---|---|",
        *[f"| {c['chunk']} | {c['attempted']} | {c['kept_rate']:.1%} | {c['label_rejected']} | {c['chunk_cost_usd']:.4f} | {c['running_cost_usd']:.4f} | {c['cache_hit']:.1%} | {c['stopped'] or ''} |" for c in chunks], "",
        "## Per family: every task that contains the family (checker verdict; `kept` = after the label filter)", "",
        *_table(a["family"], ("n", "passed", "kept"), "family"), "",
        "## Single-family tasks only", "", *_table(a["single"], ("n", "passed", "kept"), "family"), "",
        "## By number of families", "", *_table(a["size"], ("n", "kept"), "families in the task"), "",
        "## Unsupported tasks per category, after filtering (top-up from the oracle when kept < 20)", "",
        *_table(a["unsupported"], ("n", "passed", "kept"), "intent"), "",
        "### What the teacher put in `nearest_supported` on passed unsupported tasks", "", "| intent | teacher's label | accepted |", "|---|---|---|",
        *[f"| {i} | {g} | {'yes' if ok else '**no (filtered)**'} | x{n}" for (i, g, ok), n in sorted(a["labels"].items(), key=str)], "",
        "## Ambiguous tasks per category", "", *_table(a["ambiguous"], ("n", "kept"), "intent"), "",
    ]  # fmt: skip
    lines = [x.replace(" | x", " | ") if x.startswith("| unsup.") else x for x in lines]
    out.mkdir(parents=True, exist_ok=False)
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    for f in ("chunks.jsonl", "END.json", "DATA_CARD.json"):
        if (work / f).exists():
            (out / f).write_bytes((work / f).read_bytes())
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    (out / "manifest.json").write_text(json.dumps({
        "created": datetime.now(UTC).isoformat(timespec="seconds"), "commit": sha, "run": work.name,
        "episodes": t["n"], "passed": t["passed"], "kept": t["kept"], "cost_usd": round(cost, 6), "cache_hit": round(cache, 4),
        "prompt_sha256": config.SYSTEM_PROMPT_V1_SHA256, "taskgen_seed": config.TASKGEN_SEED, "ended": end["why"],
        "trajectories_sha256": hashlib.sha256((work / "trajectories.jsonl").read_bytes()).hexdigest(),
    }, indent=1) + "\n")  # fmt: skip
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    print(
        report(config.DATA_DIR / "teacher" / a.name, load_tasks("train", purpose="teacher"), a.out)
    )


if __name__ == "__main__":
    main()
