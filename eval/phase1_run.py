"""Phase 1 test-run driver (A2) and report builder (A5): ONE path for the real run and its dry run.

  uv run python -m eval.phase1_run run    --runs-root reports/<date>-phase-1-runs [--systems B0 B2 M1 M3 X1]
  uv run python -m eval.phase1_run report --runs-root reports/<date>-phase-1-runs --out reports/<date>-phase-1
  ... both with `--dry-run-dev --limit 10` to rehearse on the first 10 DEV tasks (no test split is read, no lock is taken,
      X1 capped at $0.01); the same scripts, flags, budget guard and report writer are used.

`run`: preflight (B0 frozen hash, test-file hashes vs data/tasks/MANIFEST.json, preregistration FINAL) -> per system: serve
the GGUF in llama.cpp under a memory cap, `eval.run_baseline` once per split (it takes the single-run test lock). X1 runs
only off-peak, prints its estimate first and stops at the cap. `report`: `final_report` + manifest.json (hashes, versions, costs).
"""

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import time
import tomllib
import urllib.request
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from eval import run_baseline
from eval.final_report import final_report
from eval.testlock import LEDGER as TEST_LEDGER
from training import config
from training.taskgen.loader import load_tasks
from training.teacher.budget import BudgetGuard
from training.teacher.generate import is_offpeak

ROOT = config.REPO_ROOT
MODELS = config.DATA_DIR / "models"
LLAMA_SERVER = config.DATA_DIR / "tools" / "llama-b12032" / "llama-b12032" / "llama-server"
CFG = ROOT / "eval" / "configs"
# system -> (model config, GGUF file, checkpoint id that keys the single-run lock)
SYSTEMS = {
    "B0": (CFG / "b0-regex.toml", None, "b0-frozen-paraphrase"),
    "B2": (CFG / "qwen3-0.6b-v1.toml", MODELS / "Qwen3-0.6B-Q8_0.gguf", "qwen3-0.6b-q8_0"),
    "M1": (CFG / "m1-0.6b-q8.toml", MODELS / "m1-gguf" / "ffmpeg-agent-m1-0.6b-q8_0.gguf", "m1-0.6b-q8_0"),
    "M3": (CFG / "grpo-m3-ckpt60-q8.toml", MODELS / "grpo-m3-ckpt60-gguf" / "grpo-m3-ckpt60-q8_0.gguf", "grpo-m3-ckpt60-q8_0"),
    "X1": (CFG / "x1-deepseek-v1.toml", None, "deepseek-v4-flash"),
}  # fmt: skip
SPLITS = ("test-iid", "test-phrasing", "test-compositional")  # test-iid first: Q4 needs it
DEDUP = ROOT / "reports" / "2026-11-20-leakage-audit" / "exact-duplicates.json"
DEDUP_IDS_SHA256 = "342adb9d68313018f49a469ee71911dd01cb066f8ca659ca8e66aebb8b884a7c"  # pinned in the preregistration
MEMORY_MAX = "4G"  # /tmp is RAM and the desktop has been OOM-killed before (memory note)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def log(root: Path, msg: str) -> None:
    line = f"{datetime.now(UTC).isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with (root / "run.log").open("a") as f:
        f.write(line + "\n")


def preflight(dry: bool) -> None:
    if sha256_file(ROOT / "eval" / "b0_regex.py") != config.B0_FROZEN_SHA256:
        sys.exit("B0 source does not match the frozen hash: refusing to run")
    if not dry:
        manifest = json.loads((config.DATA_DIR / "tasks" / "MANIFEST.json").read_text())["splits"]
        for sp in SPLITS:
            got = sha256_file(config.DATA_DIR / "tasks" / sp / "v1.jsonl")
            if got != manifest[sp]["sha256"]:
                sys.exit(f"{sp} task file hash differs from MANIFEST.json")
        if "Phase 1 status: FINAL" not in (ROOT / "eval" / "PREREGISTRATION.md").read_text():
            sys.exit("preregistration is not FINAL")


@contextmanager
def serve(system: str, root: Path):
    cfg_path, gguf, _ = SYSTEMS[system]
    with serve_gguf(cfg_path, gguf, root, system):
        yield


@contextmanager
def serve_gguf(cfg_path: Path, gguf: Path | None, root: Path, name: str):
    """llama-server for one model config under a memory cap; no server for a system without a GGUF (B0, X1)."""
    if gguf is None:
        yield
        return
    cfg = tomllib.loads(cfg_path.read_text())
    port = cfg["base_url"].rsplit(":", 1)[1].split("/")[0]
    argv = ["systemd-run", "--user", "--scope", "-q", "-p", f"MemoryMax={MEMORY_MAX}", str(LLAMA_SERVER),
            "-m", str(gguf), "--host", "127.0.0.1", "--port", port, *shlex.split(cfg["server_args"])]  # fmt: skip
    logf = (root / f"server-{name}.log").open("w")
    proc = subprocess.Popen(argv, stdout=logf, stderr=subprocess.STDOUT, cwd=ROOT)
    try:
        for _ in range(180):
            try:
                if (
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).status
                    == 200
                ):
                    break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError(f"llama-server for {name} did not come up")
        yield
    finally:
        proc.terminate()  # this pid only; never `pkill -f`
        proc.wait(timeout=60)
        logf.close()


def x1_remaining(root: Path) -> float:
    spent = sum(
        json.loads(m.read_text())["cost_usd"] for m in (root / "runs").glob("X1-*/manifest.json")
    )
    return config.X1_TEST_CAP_USD - spent


def do_run(a: argparse.Namespace) -> None:
    root, dry = a.runs_root, a.dry_run_dev
    (root / "runs").mkdir(parents=True, exist_ok=True)
    preflight(dry)
    log(root, f"start dry={dry} systems={a.systems} limit={a.limit}")
    splits = ("dev",) if dry else SPLITS
    for system in a.systems:
        cfg_path, _, ckpt = SYSTEMS[system]
        with serve(system, root):
            for sp in splits:
                if (
                    root / "STOP"
                ).exists():  # `touch <runs-root>/STOP`: stop cleanly at the next split boundary
                    log(
                        root,
                        "STOP file found: stopping at a split boundary; re-run the same command to resume",
                    )
                    return
                prior = root / "runs" / f"{system}-{sp}"
                if (
                    prior / "manifest.json"
                ).exists():  # run_baseline writes the manifest last: the split is finished
                    log(root, f"skip {system} {sp}: finished")
                    continue
                if (
                    prior.exists()
                ):  # started but never finished: its lock is spent, so this needs a human decision
                    sys.exit(
                        f"{prior} is a partial run (no manifest.json). Re-running needs a written supersede reason."
                    )
                tasks_file = (
                    config.DATA_DIR / "tasks" / ("dev/v1.jsonl" if dry else f"{sp}/v1.jsonl")
                )
                argv = ["--system", system, "--model-config", str(cfg_path), "--tasks", str(tasks_file),
                        "--out", str(root / "runs" / f"{system}-{sp}")]  # fmt: skip
                if a.limit:
                    argv += ["--limit", str(a.limit)]
                if not dry:
                    argv += ["--checkpoint", ckpt]
                if system == "X1":
                    n = a.limit or len(tasks_file.read_text().splitlines())
                    cap = 0.01 if dry else x1_remaining(root)
                    est = n * config.X1_EST_COST_PER_TASK_USD
                    life = config.BUDGET_LIFETIME_USD - BudgetGuard(config.LEDGER_PATH, config.BUDGET_LIFETIME_USD, cap, "estimate").spent()  # fmt: skip
                    log(
                        root,
                        f"X1 {sp}: {n} tasks, estimate ${est:.4f}, cap left ${cap:.4f}, lifetime left ${life:.4f}",
                    )
                    if not is_offpeak(datetime.now(UTC)):
                        sys.exit("X1 refuses to run inside a DeepSeek peak window")
                    if est > cap or est > life:
                        log(root, f"X1 {sp}: estimate exceeds the cap: NOT RUN")
                        continue
                    argv += ["--budget-usd", f"{cap:.4f}"]
                log(root, f"run {system} {sp}")
                run_baseline.main(argv)
    log(root, "done")


def do_report(a: argparse.Namespace) -> None:
    root, dry = a.runs_root, a.dry_run_dev
    dirs = {
        s: {sp: d for sp in SPLITS if (d := root / "runs" / f"{s}-{'dev' if dry else sp}").exists()}
        for s in SYSTEMS
    }  # fmt: skip
    dirs = {s: v for s, v in dirs.items() if v}
    if dry:
        tasks = load_tasks("dev", "dev-eval")
        ids = {json.loads(x)["task_id"] for x in (next(iter(dirs.values()))[SPLITS[0]] / "results.jsonl").read_text().splitlines()}  # fmt: skip
        tasks_by_split = {sp: {t["id"]: t for t in tasks if t["id"] in ids} for sp in SPLITS}
    else:
        tasks_by_split = {sp: {t["id"]: t for t in load_tasks(sp, "test-eval")} for sp in SPLITS}
    have = lambda s, sp: s in dirs and sp in dirs[s]  # noqa: E731
    comps, not_run = [], []
    for c in config.PREREG_COMPARISONS:
        needed = [(c[1], sp) for sp in c[3].split("+")] + [(c[2], sp) for sp in c[3].split("+")]
        (comps if all(have(s, sp) for s, sp in needed) else not_run).append(c)
    dedup = None
    if not dry and DEDUP.exists():
        ids_ = json.loads(DEDUP.read_text())["test-iid"]["dedup_ids"]
        if hashlib.sha256("\n".join(ids_).encode()).hexdigest() != DEDUP_IDS_SHA256:
            sys.exit("dedup id list does not match the hash pinned in the preregistration")
        dedup = frozenset(ids_)
    out = final_report(
        dirs, tasks_by_split, comps, a.out,
        ledger=None if dry else TEST_LEDGER,
        checkpoints={s: SYSTEMS[s][2] for s in dirs}, iid_dedup_ids=dedup,
    )  # fmt: skip
    run_manifests = {f"{s}-{sp}": json.loads((d / "manifest.json").read_text()) for s, v in dirs.items() for sp, d in v.items()}  # fmt: skip
    first = next(iter(run_manifests.values()))
    manifest = {
        "report": "phase-1" + ("-DRY-RUN-on-10-dev-tasks" if dry else ""),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip(),  # fmt: skip
        "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT).stdout.strip()),  # fmt: skip
        "utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "protocol_version": config.PROTOCOL_VERSION,
        "ffmpeg_version": first["ffmpeg_version"],
        "hardware": first["hardware"],
        "seeds": {"bootstrap": config.BOOTSTRAP_SEED, "llama_server": 20261115, "training": "single seed"},
        "preregistration": {"procedure": config.PREREG_PROCEDURE, "alpha": config.PREREG_ALPHA,
                            "order": [c[0] for c in config.PREREG_COMPARISONS], "not_run": [c[0] for c in not_run],
                            "sha256": sha256_file(ROOT / "eval" / "PREREGISTRATION.md")},  # fmt: skip
        "hashes": {
            "b0_regex.py": sha256_file(ROOT / "eval" / "b0_regex.py"),
            "system_prompt": config.SYSTEM_PROMPT_V1_SHA256,
            "models": {s: sha256_file(SYSTEMS[s][1]) for s in dirs if SYSTEMS[s][1]},
            "task_files": {} if dry else {sp: sha256_file(config.DATA_DIR / "tasks" / sp / "v1.jsonl") for sp in SPLITS},
            "run_tasks_sha256": {k: v["tasks_sha256"] for k, v in run_manifests.items()},
        },
        "runs": {k: {"n_tasks": v["n_tasks"], "cost_usd": v["cost_usd"], "stopped_reason": v["stopped_reason"], "git_dirty": v["git_dirty"]} for k, v in run_manifests.items()},  # fmt: skip
        "cost_usd_total": sum({str(d): json.loads((d / "manifest.json").read_text())["cost_usd"] for v in dirs.values() for d in v.values()}.values()),  # a dry run maps one dir to several pseudo-splits: count it once
        "llama_server": subprocess.run([str(LLAMA_SERVER), "--version"], capture_output=True, text=True).stderr.strip().splitlines()[:1],  # fmt: skip
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {out}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "report"):
        p = sub.add_parser(name)
        p.add_argument("--runs-root", type=Path, required=True)
        p.add_argument("--dry-run-dev", action="store_true")
        if name == "run":
            p.add_argument("--systems", nargs="+", default=list(SYSTEMS), choices=list(SYSTEMS))
            p.add_argument("--limit", type=int, default=None)
        else:
            p.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    {"run": do_run, "report": do_report}[a.cmd](a)


if __name__ == "__main__":
    main()
