"""Audit: did the old allow-list validator (backslash-in-quotes bypass) ever accept a recorded run action
that the fixed one rejects?  Read-only over reports/ and data/; deterministic (sorted walk, no randomness).

    uv run python -m eval.audit_validator_bypass --out reports/2026-11-25-validator-audit

The OLD validator is loaded from git (OLD_REV), never from a copy. A "run action" is any JSON object with
action == "run" and a list of string args, found at any depth, including inside string fields (assistant text,
chat messages). An "episode" is one JSONL line / JSON file holding at least one run action. Input/output ids are
taken from the args themselves, so only the argument rules are compared.
"""

import argparse
import json
import re
import subprocess
import types
from collections import defaultdict
from pathlib import Path

from tokenizers import Tokenizer

from training.env import validator as new

ROOT = Path(__file__).resolve().parents[1]
OLD_REV = "ca3467f~1"  # the commit just before the fix
SKIP_DIRS = (
    "data/models",
    "data/mlc",
    "data/corpus",
    "data/tools",
    "data/scratch",
    "data/browser-profile-cg",
)
QUOTED_BACKSLASH = re.compile(
    r"'[^']*\\[^']*'"
)  # grep-style: a backslash between two single quotes
DEC = json.JSONDecoder()
TOK = Tokenizer.from_file(
    str(ROOT / "data/models/m1-merged/ffmpeg-agent-m1-0.6b/tokenizer.json")
)  # Qwen3, same for all


def load_old() -> types.ModuleType:
    src = subprocess.run(
        ["git", "show", f"{OLD_REV}:training/env/validator.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    mod = types.ModuleType("validator_old")
    exec(compile(src, "validator_old", "exec"), mod.__dict__)
    return mod


def find_runs(obj, out: list) -> None:
    if isinstance(obj, dict):
        a = obj.get("args")
        if (
            obj.get("action") == "run"
            and isinstance(a, list)
            and all(isinstance(x, str) for x in a)
        ):
            out.append(a)
        for v in obj.values():
            find_runs(v, out)
    elif isinstance(obj, list):
        for v in obj:
            find_runs(v, out)
    elif isinstance(obj, str) and "action" in obj and "run" in obj:
        for m in re.finditer(r"\{", obj):  # JSON action embedded in text
            try:
                d, _ = DEC.raw_decode(obj, m.start())
            except ValueError:
                continue
            find_runs(d, out)


def ids(args: list[str]) -> tuple[list[str], list[str]]:
    i = [m.group(1) for a in args if (m := re.fullmatch(r"\{in:([^}]*)\}", a))]
    o = [m.group(1) for a in args if (m := re.fullmatch(r"\{out:([^}]*)\}", a))]
    return i, o


def ok(mod, args: list[str]) -> bool:
    i, o = ids(args)
    return mod.validate_run(args, i, o, known_inputs=set(i), known_outputs=set(o)).ok


def _decode_sft(rec, tok):
    """SFT examples are token ids; decode the supervised (label != -100) tokens back to the assistant text."""
    if isinstance(rec, dict) and "input_ids" in rec and "labels" in rec:
        return tok.decode([t for t in rec["labels"] if t != -100], skip_special_tokens=False)
    return rec


def records(path: Path):
    if path.suffix == ".jsonl":
        for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            try:
                yield f"{path}:{n}", _decode_sft(json.loads(line), TOK)
            except ValueError:
                pass
    else:
        try:
            yield str(path), json.loads(path.read_text(errors="replace"))
        except ValueError:
            pass


def group(rel: str) -> str:
    p = rel.split("/")
    return "/".join(p[: 3 if p[0] == "data" else 2])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    out_dir = ROOT / ap.parse_args().out
    old = load_old()
    stats: dict[str, dict] = defaultdict(
        lambda: {
            "files": 0,
            "episodes": 0,
            "run_actions": 0,
            "backslash_in_quotes": 0,
            "affected_actions": 0,
        }
    )
    affected, seen = [], set()
    for base in ("reports", "data"):
        for path in sorted((ROOT / base).rglob("*")):
            rel = path.relative_to(ROOT).as_posix()
            if (
                not path.is_file()
                or path.suffix not in (".json", ".jsonl")
                or (
                    path.suffix == ".json" and rel.startswith(SKIP_DIRS)
                )  # configs/weights; every .jsonl is read
                or "tokenizer" in path.name
                or rel.startswith(out_dir.relative_to(ROOT).as_posix())
                or path.stat().st_size > 600_000_000
            ):
                continue
            s = stats[group(rel)]
            s["files"] += 1
            for where, rec in records(path):
                runs: list = []
                find_runs(rec, runs)
                if not runs:
                    continue
                s["episodes"] += 1
                for a in runs:
                    s["run_actions"] += 1
                    s["backslash_in_quotes"] += any(QUOTED_BACKSLASH.search(x) for x in a)
                    if ok(old, a) and not ok(new, a):
                        s["affected_actions"] += 1
                        affected.append({"where": where, "args": a})
                    seen.add(json.dumps(a))
    tot = {k: sum(v[k] for v in stats.values()) for k in next(iter(stats.values()))}
    res = {
        "old_rev": OLD_REV,
        "total": tot,
        "unique_run_arg_lists": len(seen),
        "affected": affected,
        "datasets": dict(sorted(stats.items())),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(res, indent=1) + "\n")
    rows = "\n".join(
        f"| {k} | {v['files']} | {v['episodes']} | {v['run_actions']} | {v['backslash_in_quotes']} | {v['affected_actions']} |"
        for k, v in sorted(stats.items())
        if v["run_actions"]
    )
    (out_dir / "summary.md").write_text(
        f"# Validator bypass audit\n\nOld validator: `git show {OLD_REV}:training/env/validator.py`; new: working tree. "
        f"Script: `eval/audit_validator_bypass.py`.\n\nTotal: {tot['episodes']} episodes, {tot['run_actions']} run actions "
        f"({len(seen)} unique arg lists), {tot['backslash_in_quotes']} with a backslash inside single quotes, "
        f"**{tot['affected_actions']} affected** (old accepted, new rejects).\n\n"
        "| dataset | files | episodes | run actions | backslash in quotes | affected |\n|---|---|---|---|---|---|\n"
        f"{rows}\n\nAffected: {json.dumps(affected, indent=1) if affected else 'none'}\n"
    )
    print(json.dumps({"total": tot, "unique": len(seen)}))


if __name__ == "__main__":
    main()
