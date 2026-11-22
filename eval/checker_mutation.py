"""Checker mutation self-test (EVALUATION §6, A4): outputs that the gold spec forbids must FAIL the check.

uv run python -m eval.checker_mutation --out reports/<date>-checker-mutation --work <scratch dir> [--n 60] [--seed 20261115]

For a seeded sample of dev tasks with a reference solution: run the reference (it must pass its gold spec: the
unmutated control), then derive MUTANTS from the passing output with ffmpeg, each breaking ONE constrained field of
the spec, and run the checker again. A mutant that the checker still passes is a SURVIVOR: a blind spot, reported, never
hidden (RULES §4.2). A mutation is applied only when the spec constrains the field it breaks (so every applicable
mutant has a known right answer: fail). Dev tasks only; arguments are lists, never shell strings.
"""

import argparse
import json
import random
import subprocess
from pathlib import Path

from eval.run_baseline import load_corpus
from training import config
from training.env.checker import check
from training.env.executor import execute, output_path_for
from training.env.probe import probe
from training.taskgen.loader import load_tasks


def _video(o: dict) -> dict:
    return {k: v for k, v in (o.get("video") or {}).items() if v is not None}


def _audio(o: dict) -> dict:
    return {k: v for k, v in (o.get("audio") or {}).items() if v is not None}


# name -> (applies(spec output, ok probe), ffmpeg args after `-i <ok output>` (without the output path), output extension or None)
MUTANTS = {
    "truncate_half": (lambda o, p: True, lambda o, p: ["-t", str(round(p["duration_s"] / 2, 3)), "-c", "copy"], None),
    "wrong_width": (lambda o, p: "width" in _video(o), lambda o, p: ["-vf", f"scale={_video(o)['width'] + 32}:-2", "-c:a", "copy"], None),
    "drop_audio": (lambda o, p: _audio(o).get("present") is True, lambda o, p: ["-an", "-c:v", "copy"], None),
    "wrong_container_mkv": (lambda o, p: o.get("container") == "mp4", lambda o, p: ["-c", "copy"], ".mkv"),
    "wrong_fps": (lambda o, p: "fps" in _video(o), lambda o, p: ["-vf", f"fps={_video(o)['fps'] * 2}", "-c:a", "copy"], None),
    "louder_audio": (lambda o, p: "loudness_lufs" in _audio(o), lambda o, p: ["-af", "volume=10dB", "-c:v", "copy"], None),
    "rotate_180": (lambda o, p: "rotation" in _video(o), lambda o, p: ["-vf", "hflip,vflip", "-c:a", "copy"], None),
}  # fmt: skip
# mutants that need no ffmpeg: a bad file, or a re-encoding run claimed as lossless
FILE_MUTANTS = ("empty_file", "garbage_file")
RUN_MUTANT = "lossless_claimed_but_reencoded"


def ffmpeg(args: list[str]) -> bool:
    r = subprocess.run(
        [str(config.FFMPEG_BIN), "-y", "-v", "error", *args], capture_output=True, timeout=300
    )
    return r.returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=config.BOOTSTRAP_SEED)
    ap.add_argument("--work", type=Path, required=True, help="scratch dir (not /tmp: it is RAM)")
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    tasks = [t for t in load_tasks("dev", "dev-eval") if t["gold_spec"] and t["reference_runs"]
             and all(o["kind"] == "video" for o in t["gold_spec"]["outputs"])]  # fmt: skip
    tasks = random.Random(a.seed).sample(sorted(tasks, key=lambda t: t["id"]), min(a.n, len(tasks)))
    corpus, stats, survivors, control_fail = load_corpus(), {}, [], []

    def tally(name: str, killed: bool, tid: str) -> None:
        s = stats.setdefault(name, {"applicable": 0, "killed": 0})
        s["applicable"] += 1
        s["killed"] += killed
        if not killed:
            survivors.append({"mutant": name, "task_id": tid})

    for i, t in enumerate(tasks):
        gold = {o["id"]: o for o in t["gold_spec"]["outputs"]}
        run = t["reference_runs"][-1]
        work = a.work / f"{i:03d}"
        res = execute(run, input_paths={c: corpus[c] for c in t["inputs"]}, output_paths={oid: output_path_for(work, o) for oid, o in gold.items()})  # fmt: skip
        probes = [probe(corpus[c]) for c in t["inputs"]]
        kw = {
            "input_probe": probes[0],
            "input_probes": probes,
            "input_paths": [corpus[c] for c in t["inputs"]],
        }
        oid, o = next(iter(gold.items()))
        if (
            not res.ok
            or oid not in res.outputs
            or not check(o, res.outputs[oid], run_args=run["args"], **kw)["passed"]
        ):
            control_fail.append(
                t["id"]
            )  # the unmutated reference must pass; otherwise this task says nothing
            continue
        ok_path, ok_probe = res.outputs[oid], probe(res.outputs[oid])
        for name, (applies, mk, ext) in MUTANTS.items():
            if not applies(o, ok_probe):
                continue
            out = ok_path.with_name(f"mut-{name}{ext or ok_path.suffix}")
            if ffmpeg(["-i", str(ok_path), *mk(o, ok_probe), str(out)]):
                tally(name, not check(o, out, run_args=run["args"], **kw)["passed"], t["id"])
        for name in FILE_MUTANTS:
            out = ok_path.with_name(f"mut-{name}{ok_path.suffix}")
            out.write_bytes(b"" if name == "empty_file" else random.Random(i).randbytes(4096))
            tally(name, not check(o, out, run_args=run["args"], **kw)["passed"], t["id"])
        if o.get("lossless") is True:
            reenc = ["-i", "{in:x}", "-c:v", "libx264", "{out:out1}"]
            tally(RUN_MUTANT, not check(o, ok_path, run_args=reenc, **kw)["passed"], t["id"])
    a.out.mkdir(parents=True)
    result = {
        "seed": a.seed,
        "tasks_sampled": len(tasks),
        "control_failures": control_fail,
        "mutants": stats,
        "survivors": survivors,
    }
    (a.out / "results.json").write_text(json.dumps(result, indent=1) + "\n")
    lines = ["# Checker mutation self-test (dev tasks, seeded sample)", "",
            f"{len(tasks)} tasks sampled; {len(tasks) - len(control_fail)} reference outputs passed their own spec and were mutated; unmutated control failures: {len(control_fail)}.", "",
            "| mutant | applicable | killed (check failed) | survivors |", "|---|---|---|---|"]  # fmt: skip
    lines += [
        f"| {k} | {v['applicable']} | {v['killed']} | {v['applicable'] - v['killed']} |"
        for k, v in stats.items()
    ]
    lines += [
        "",
        "A survivor is a checker blind spot: "
        + (f"{len(survivors)} found, listed in results.json." if survivors else "none found."),
    ]
    (a.out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
