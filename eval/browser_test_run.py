"""The browser row of Phase 1 (Amendment 4): M3 Q5_K_M in the browser (wllama), once per test split, as an EXTRA descriptive row.

    uv run python -m eval.browser_test_run --runs-root reports/<date>-phase-1-browser-row --dry-run-dev   # dev sample, no lock
    uv run python -m eval.browser_test_run --runs-root reports/<date>-phase-1-browser-row               # the three test splits

Resumable per split like eval/phase1_run.py: a split with a manifest is skipped, a started-but-unfinished split stops
the run (its lock is spent: re-running needs a written supersede reason from the owner), `touch <runs-root>/STOP`
stops cleanly at the next split boundary. Nothing here changes a checker, metric or selection.

Safety order for every test split: (1) the working trees are clean and the task file's sha256 equals the pinned one;
(2) the preregistration text contains the frozen configuration string; (3) the bridge is up and its recorded
environment equals the frozen configuration (`verify_env`); ONLY THEN (4) the single-run lock is acquired and
(5) the harness runs. A mismatch at steps 1 to 3 aborts before the lock, so it costs nothing.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from eval.browser_parity import GGUF_DIR, SITE, Bridge, BrowserPolicy, serve_bridge
from eval.hf_parity import sample_ids
from eval.quant_parity import SEED, N
from eval.run_baseline import load_corpus, run_baseline
from eval.testlock import acquire_test_run
from training import config
from training.env.constrained import load_prompt
from training.taskgen.loader import load_tasks

SYSTEM = "M3-browser"  # the lock's system name; the harness's run-budget key is "M3"
SPLITS = ("test-iid", "test-phrasing", "test-compositional")
CFG = config.REPO_ROOT / "eval" / "configs" / "browser-wllama.toml"
PREREG = config.REPO_ROOT / "eval" / "PREREGISTRATION.md"
PINNED_TASK_SHA256 = {  # Amendment 3: equal to data/tasks/MANIFEST.json
    "test-iid": "bd01e887c032921949e1eb6f373fd41164e72ac6b956424ed0a55e7bd1f83470",
    "test-compositional": "19f599f1c570a19f7d41925dc4e1fa0232e3118f7defaadb71ef4faa50f17c9e",
    "test-phrasing": "86188225ded5abb8749690e465a7079c6900272ede113e3c10e3d7ee6748212e",
}
GPU_FLAGS = ["--enable-unsafe-webgpu", "--enable-features=Vulkan", "--use-angle=vulkan"]
FROZEN = {  # Amendment 4. Any change is a different system and needs its own lock.
    "model": "grpo-m3-ckpt60",
    "quant": "Q5_K_M",
    "gguf_name": "grpo-m3-ckpt60-q5_k_m.gguf",
    "gguf_sha256": "bbf439b749c02c04b5227ab93fb1430263a7c567c15552b6e12ae3836cde1e11",
    "wllama": "4.0.0",
    "libllama": "b12637-0b51bb2",
    "chromium": "159.0.8154.6",
    "playwright": "1.65.1",
    "mode": "gpu",
    "adapter_vendor": "nvidia",
    "chromium_args": GPU_FLAGS,
    "kv_cache": {"k": "q8_0", "v": "q8_0", "flash_attn": "true"},
    "n_ctx": 8192,
}


def checkpoint_string(f: dict = FROZEN) -> str:
    """The lock key (reports/TEST_RUNS.jsonl `checkpoint`), frozen in Amendment 4."""
    return (
        f"{f['model']}-{f['quant'].lower()}[sha256:{f['gguf_sha256'][:8]}]"
        f"+wllama-{f['wllama']}[libllama-{f['libllama']}]+chromium-{f['chromium']}"
        f"+webgpu+kv-{f['kv_cache']['k']}-fa+n_ctx{f['n_ctx']}"
    )


def verify_env(rec: dict, f: dict = FROZEN) -> list[str]:
    """Mismatches between the bridge's recorded environment (env.json) and the frozen configuration; empty = identical."""
    bad = []
    gpu = (rec.get("env") or {}).get("gpu") or {}
    checks = {
        "wllama": (rec.get("wllama"), f["wllama"]),
        "libllama": ((rec.get("env") or {}).get("libllama"), f["libllama"]),
        "chromium": (rec.get("chromium"), f["chromium"]),
        "playwright": (rec.get("playwright"), f["playwright"]),
        "mode": (rec.get("mode"), f["mode"]),
        "model file": (rec.get("model"), f["gguf_name"]),
        "n_ctx": (rec.get("n_ctx"), f["n_ctx"]),
        "n_ctx loaded": ((rec.get("load") or {}).get("n_ctx"), f["n_ctx"]),
        "kv cache": (rec.get("kv_cache"), f["kv_cache"]),
        "chromium args": (rec.get("chromium_args"), f["chromium_args"]),
        "adapter vendor": (gpu.get("vendor"), f["adapter_vendor"]),
    }
    bad += [
        f"{k}: got {got!r}, frozen {want!r}" for k, (got, want) in checks.items() if got != want
    ]
    if gpu.get("isFallbackAdapter") is not False:
        bad.append(
            f"adapter is a fallback or unknown (isFallbackAdapter={gpu.get('isFallbackAdapter')!r})"
        )
    if not (rec.get("load") or {}).get("multithread"):
        bad.append("runtime is not multithreaded")
    if (rec.get("memory_cap") or {}).get("memory_max") in (None, "max"):
        bad.append("no memory cap in force")
    return bad


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(repo: Path, *a: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *a], capture_output=True, text=True
    ).stdout.strip()


def tracked_dirty(repo: Path) -> bool:
    """Uncommitted changes to tracked files (untracked report folders are expected and ignored)."""
    return bool(_git(repo, "status", "--porcelain", "--untracked-files=no"))


def log(root: Path, msg: str) -> None:
    with (root / "run.log").open("a") as f:
        f.write(f"{datetime.now(UTC).isoformat(timespec='seconds')} {msg}\n")
    print(msg, flush=True)


def preflight(dry: bool) -> None:
    gguf = GGUF_DIR / FROZEN["gguf_name"]
    if sha256_file(gguf) != FROZEN["gguf_sha256"]:
        sys.exit(f"{gguf.name} does not have the frozen sha256")
    if not dry:
        text = PREREG.read_text()
        if "Phase 1 status: FINAL" not in text or checkpoint_string() not in text:
            sys.exit(
                "eval/PREREGISTRATION.md must say FINAL and contain Amendment 4 with this frozen configuration string"
            )
        for repo in (config.REPO_ROOT, SITE):
            if tracked_dirty(repo):
                sys.exit(
                    f"{repo} has uncommitted tracked changes: commit first, the run records the commits"
                )
    for sp, want in PINNED_TASK_SHA256.items():
        if sha256_file(config.DATA_DIR / "tasks" / sp / "v1.jsonl") != want:
            sys.exit(f"{sp} task file does not match the pinned sha256")


def provenance() -> dict:
    smi = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()  # fmt: skip
    return {"ffwd_commit": _git(config.REPO_ROOT, "rev-parse", "HEAD"), "ffwd_web_commit": _git(SITE, "rev-parse", "HEAD"),
            "nvidia": smi, "kernel": subprocess.run(["uname", "-r"], capture_output=True, text=True).stdout.strip()}  # fmt: skip


def run_split(root: Path, split: str, dry: bool, mem_max: str, port: int) -> None:
    name = f"{SYSTEM}-{'dev' if dry else split}"
    dest = root / "runs" / name
    if (dest / "manifest.json").exists():
        log(root, f"skip {name}: finished")
        return
    if dest.exists():
        sys.exit(
            f"{dest} is a partial run (no manifest.json). Its lock is spent: re-running needs a written supersede reason."
        )
    cfg = tomllib.loads(CFG.read_text())
    if dry:
        all_tasks = load_tasks("dev", "dev-eval")
        ids = set(sample_ids(all_tasks, N, SEED))
        tasks = [t for t in all_tasks if t["id"] in ids]
        raw = ("".join(json.dumps(t) + "\n" for t in tasks)).encode()
    else:
        raw = (config.DATA_DIR / "tasks" / split / "v1.jsonl").read_bytes()
        tasks = [json.loads(x) for x in raw.decode().splitlines()]
        if {t["split"] for t in tasks} != {split}:
            sys.exit(f"{split} task file contains other splits")
    br = Bridge(gguf=GGUF_DIR / FROZEN["gguf_name"], mode="gpu", ctx=FROZEN["n_ctx"], kv=FROZEN["kv_cache"]["k"],
                bridge_dir=root / "bridges" / name, log_path=root / "bridges" / f"{name}.log", name=name, port=port, mem_max=mem_max)  # fmt: skip
    ckpt = checkpoint_string()
    with serve_bridge(br) as url:
        rec = json.loads((br.bridge_dir / "env.json").read_text())
        if bad := verify_env(rec):
            sys.exit(
                "the browser environment differs from the frozen configuration (no lock taken):\n  "
                + "\n  ".join(bad)
            )
        if not dry:
            acquire_test_run(
                SYSTEM, ckpt, split
            )  # BEFORE the run: a crash cannot be retried quietly
        log(root, f"run {name} ({len(tasks)} tasks)")
        run_baseline(
            system="M3", policy=BrowserPolicy(url, name), tasks=tasks, out=dest, corpus=load_corpus(),
            meta={"model": name, "lock_system": SYSTEM, "checkpoint": ckpt, "frozen_config": FROZEN, "quant": FROZEN["quant"],
                  "runtime": "wllama in Chromium (WebGPU); see bridges/<name>/env.json", "temperature": 0.0,
                  "model_config": str(CFG), "system_prompt": cfg["system_prompt"], "constrained_decoding": False, "require_spec": True,
                  "stop_after_ask": True, "dry_run_dev": dry, "mem_max": mem_max, **provenance()},
            tasks_sha256=hashlib.sha256(raw).hexdigest(), system_prompt_text=load_prompt(cfg["system_prompt"]),
            require_spec=True, stop_after_ask=True,
        )  # fmt: skip
    log(root, f"done {name}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", type=Path, required=True)
    ap.add_argument(
        "--dry-run-dev",
        action="store_true",
        help="the 100-task dev sample through the same code path; no lock",
    )
    ap.add_argument("--mem-max", default="6G")
    ap.add_argument("--bridge-port", type=int, default=8123)
    a = ap.parse_args(argv)
    (a.runs_root / "runs").mkdir(parents=True, exist_ok=True)
    preflight(a.dry_run_dev)
    log(a.runs_root, f"start dry={a.dry_run_dev} checkpoint={checkpoint_string()}")
    for split in ("dev",) if a.dry_run_dev else SPLITS:
        if (a.runs_root / "STOP").exists():
            log(
                a.runs_root,
                "STOP file found: stopping at a split boundary; re-run the same command to resume",
            )
            return
        run_split(a.runs_root, split, a.dry_run_dev, a.mem_max, a.bridge_port)
    log(a.runs_root, "all splits finished")


if __name__ == "__main__":
    main()
