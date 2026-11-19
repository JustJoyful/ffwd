"""Recovery-start tasks (pilot, owner instruction 20 Nov 2026): the episode opens with the gold spec and a PERTURBED
reference run that the checker verifiably fails, and the policy must produce the fix.

uv run python -m training.taskgen.recovery --tasks <tasks.jsonl> --out <dir> [--n 300] [--workers 3]

M1 mostly repeats a failing command instead of using the checker's feedback (reports/2026-11-20-m1-dev-failures); a
recovery start trains and measures exactly that, and it removes the "first command already right" shortcut that makes 94%
of train tasks too easy.

Guarantees (tests: tests/taskgen/test_recovery.py), asserted by construction for every emitted task:
* the BASE reference run passes its gold spec (re-verified here, not trusted);
* the PERTURBED run was executed, ran to completion, and the checker reported at least one failed field;
* the scripted opening is `[spec action (the gold spec), run action (the perturbed args)]`, nothing else.
Train and dev tasks only (a task whose split is a test split is refused). Task ids get the suffix `-rec`.
"""

import argparse
import hashlib
import json
import random
import re
import subprocess
import tempfile
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from training import config
from training.taskgen.verify import verify_task

Args = list[str]


def _val(args: Args, flag: str) -> int | None:
    return args.index(flag) + 1 if flag in args and args.index(flag) + 1 < len(args) else None


def _even(x: float) -> int:
    return max(2, round(x / 2) * 2)


def _sub_vf(pattern: str, repl: Callable[[re.Match], str]) -> Callable[[Args], Args | None]:
    """Rewrite the first match of `pattern` inside the -vf / -filter_complex / -af argument."""

    def op(args: Args) -> Args | None:
        for flag in ("-vf", "-filter_complex", "-af"):
            i = _val(args, flag)
            if i is not None and re.search(pattern, args[i]):
                out = list(args)
                out[i] = re.sub(pattern, repl, args[i], count=1)
                return out
        return None

    return op


def drop_an(args: Args) -> Args | None:
    return [a for a in args if a != "-an"] if "-an" in args else None


def halve_t(args: Args) -> Args | None:
    i = _val(args, "-t")
    if i is None:
        return None
    out = list(args)
    out[i] = f"{float(args[i]) * 0.5:g}"
    return out


def shift_ss(args: Args) -> Args | None:
    i = _val(args, "-ss")
    if i is None:
        return None
    out = list(args)
    out[i] = "1" if float(args[i]) == 0 else "0"
    return out


def drop_af(args: Args) -> Args | None:
    i = _val(args, "-af")
    return args[: i - 1] + args[i + 1 :] if i is not None else None


def loudnorm_target(args: Args) -> Args | None:
    return _sub_vf(r"loudnorm=I=-?\d+(\.\d+)?", lambda m: "loudnorm=I=-5")(args)


def bitrate_up(args: Args) -> Args | None:
    i = _val(args, "-b:v")
    if i is None or not re.fullmatch(r"\d+k", args[i]):
        return None
    out = list(args)
    out[i] = f"{int(args[i][:-1]) * 4}k"
    return out


def swap_acodec(args: Args) -> Args | None:
    i = _val(args, "-c:a")
    if i is None or args[i] not in ("aac", "libmp3lame"):
        return None
    out = list(args)
    out[i] = "libmp3lame" if args[i] == "aac" else "aac"
    return out


# (name, operator). Each returns new args or None when it does not apply; applying is only a candidate: the perturbed
# run must still be executed and fail the checker (make_recovery).
OPERATORS: tuple[tuple[str, Callable[[Args], Args | None]], ...] = (
    ("drop_an", drop_an),
    ("halve_t", halve_t),
    ("shift_ss", shift_ss),
    ("drop_af", drop_af),
    ("loudnorm_target", loudnorm_target),
    ("bitrate_up", bitrate_up),
    ("swap_acodec", swap_acodec),
    ("scale_wrong", _sub_vf(r"scale=(\d+):(\d+)", lambda m: f"scale={_even(int(m[1]) * 0.5)}:{_even(int(m[2]) * 0.5)}")),
    ("crop_wrong", _sub_vf(r"crop=(\d+):(\d+)", lambda m: f"crop={_even(int(m[1]) * 0.5)}:{_even(int(m[2]) * 0.5)}")),
    ("fps_wrong", _sub_vf(r"fps=(\d+)(?!/)", lambda m: f"fps={int(m[1]) * 2}")),
    ("frames_interval", _sub_vf(r"fps=1/(\d+)", lambda m: f"fps=1/{int(m[1]) * 3}")),
    ("speed_wrong", _sub_vf(r"setpts=PTS/(\d+(\.\d+)?)", lambda m: f"setpts=PTS/{float(m[1]) * 2:g}")),
    ("rotate_wrong", _sub_vf(r"transpose=1", lambda m: "transpose=2")),
)  # fmt: skip


def make_recovery(
    task: dict, corpus: dict[str, Path], work: Path, rng: random.Random
) -> dict | None:
    """A verified recovery start for `task`, or None if no operator produced a command that runs and fails the check."""
    if task["split"] not in ("train", "dev"):
        raise PermissionError(
            f"recovery starts are built from train or dev tasks, not {task['split']!r}"
        )
    if task["flags"]["ambiguous"] or task["flags"]["unsupported"] or not task["reference_runs"]:
        return None
    ref = task["reference_runs"][-1]
    work.mkdir(parents=True, exist_ok=True)
    base = verify_task(task, corpus, work / "base")
    if not base["passed"]:
        return None  # the reference itself must pass; a failing reference is a task bug, never a recovery start
    ops = list(OPERATORS)
    rng.shuffle(ops)
    tries = 0
    for name, op in ops:
        new_args = op(ref["args"])
        if new_args is None or new_args == ref["args"]:
            continue
        tries += 1
        if tries > config.RECOVERY_MAX_OPERATOR_TRIES:
            break
        run = ref | {"args": new_args}
        row = verify_task(task | {"reference_runs": [run]}, corpus, work / f"p{tries}")
        if (
            row["passed"]
            or not row["failed"]
            or any(f.startswith("reference run") for f in row["failed"])
        ):
            continue  # it passed, or it did not run: not a "ran, checker says no" start
        return {
            "task_id": task["id"] + "-rec",
            "base_id": task["id"],
            "operator": name,
            "perturbed_args": new_args,
            "failed": sorted(set(row["failed"])),
            "reference_passed": True,
            "opening": [
                json.dumps({"action": "spec", "spec": task["gold_spec"]}),
                json.dumps(
                    {
                        "action": "run",
                        "args": new_args,
                        "inputs": run["inputs"],
                        "outputs": run["outputs"],
                    }
                ),
            ],
        }
    return None


def recovery_task(task: dict) -> dict:
    return task | {"id": task["id"] + "-rec", "source": task["source"] + "-recovery"}


class OpeningPolicy:
    """Wraps a chat policy: the first assistant turns of a task with a scripted opening are replayed (the loop runs them
    through the real executor and checker, so the observations are real); after that the wrapped policy answers.
    Keyed by (request, input ids), like OraclePolicy: use one recovery task per base content in a run.
    """

    def __init__(self, policy, openings: dict[tuple[str, tuple[str, ...]], list[str]]):
        self.policy, self.openings = policy, openings

    def __call__(self, messages: list[dict]) -> str:
        first = json.loads(messages[1]["content"])
        opening = self.openings.get((first["request"], tuple(i["id"] for i in first["inputs"])))
        turn = (len(messages) - 2) // 2
        if opening is not None and turn < len(opening):
            return opening[turn]
        return self.policy(messages)


def openings_for(
    tasks: list[dict], rows: list[dict]
) -> dict[tuple[str, tuple[str, ...]], list[str]]:
    by_id = {r["task_id"]: r for r in rows}
    return {
        (t["request"], tuple(t["inputs"])): by_id[t["id"]]["opening"]
        for t in tasks
        if t["id"] in by_id
    }


def _jobs_dir() -> Path:
    config.JOBS_DIR.mkdir(parents=True, exist_ok=True)  # not /tmp: that is RAM-backed
    return config.JOBS_DIR


def _job(args: tuple[dict, dict[str, str]]) -> dict | None:
    task, corpus = args
    rng = random.Random(f"{config.HARD_POOL_SEED}:rec:{task['id']}")
    with tempfile.TemporaryDirectory(prefix="rec-", dir=_jobs_dir()) as d:
        return make_recovery(task, {k: Path(v) for k, v in corpus.items()}, Path(d), rng)


def main() -> None:
    from training.taskgen.clips import ClipIndex

    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, required=True, help="base tasks (train or dev jsonl)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, help="keep the first n recovery tasks (sorted by id)")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    raw = a.tasks.read_bytes()
    base = [json.loads(x) for x in raw.decode().splitlines()]
    if any(t["split"] not in ("train", "dev") for t in base):
        raise SystemExit("recovery starts are built from train or dev tasks only")
    ci = ClipIndex()
    corpus = {c.id: str(c.path) for c in ci.clips.values()}
    with ProcessPoolExecutor(a.workers) as pool:
        results = list(pool.map(_job, [(t, corpus) for t in base]))
    pairs = sorted(
        ((t, r) for t, r in zip(base, results, strict=True) if r), key=lambda p: p[0]["id"]
    )
    pairs = pairs[: a.n] if a.n else pairs
    a.out.mkdir(parents=True)
    tasks = [recovery_task(t) for t, _ in pairs]
    rows = [r for _, r in pairs]
    (a.out / "tasks.jsonl").write_text("".join(json.dumps(t, sort_keys=True) + "\n" for t in tasks))
    (a.out / "recovery.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    manifest = {
        "pool": "recovery-start",
        "base_tasks": len(base),
        "base_tasks_sha256": hashlib.sha256(raw).hexdigest(),
        "emitted": len(rows),
        "no_verified_perturbation": len(base) - sum(1 for r in results if r),
        "operators": dict(Counter(r["operator"] for r in rows)),
        "failed_fields": dict(Counter(f for r in rows for f in r["failed"]).most_common(20)),
        "all_references_passed": all(r["reference_passed"] for r in rows),
        "max_operator_tries": config.RECOVERY_MAX_OPERATOR_TRIES,
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
    }  # fmt: skip
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: manifest[k] for k in ("base_tasks", "emitted", "operators")}))


if __name__ == "__main__":
    main()
