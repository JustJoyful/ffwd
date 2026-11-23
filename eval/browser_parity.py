"""GGUF-in-the-browser parity on the SAME seeded 100 dev tasks as the MLC and GGUF parity runs (dev only).

    uv run python -m eval.browser_parity --quant Q5_K_M --mode gpu --out reports/2026-11-23-browser-gguf

Starts the ffwd-web spike bridge (spikes/wllama/run.mjs: Chromium + wllama, the prompt built by the site's own JS
port of the chat template, handed to the runtime as plain text), runs the UNCHANGED harness, checker and run budget
with a policy that sends each turn's messages to the bridge, then stops it. Greedy, 512 new tokens, system-v1.
Writes `<out>/<name>/` (results, episodes, manifest), `<out>/<name>.parity.json` (against the same quant run natively
in llama.cpp, and the Q8_0 run) and `<out>/<name>-bridge/` (environment record, per-turn timings, console log).
Refuses to overwrite. The bridge process runs under a memory cap (/tmp is RAM and the desktop has been OOM-killed).
"""

import argparse
import hashlib
import json
import statistics
import subprocess
import time
import tomllib
import urllib.request
from pathlib import Path

from eval.hf_parity import sample_ids, turns
from eval.mlc_parity import taxonomy
from eval.parity import parity
from eval.phase1_run import MODELS
from eval.quant_parity import SEED, N, side
from eval.run_baseline import load_corpus, run_baseline
from training import config
from training.env.constrained import load_prompt
from training.taskgen.loader import load_tasks

CFG = config.REPO_ROOT / "eval" / "configs" / "browser-wllama.toml"
SITE = config.REPO_ROOT.parent / "ffwd-web"
GGUF_DIR = MODELS / "grpo-m3-ckpt60-gguf"
NATIVE = (
    {  # the same quant run natively in llama.cpp on the same sample (the like-for-like reference)
        "Q4_K_M": "reports/2026-11-22-m3-q4km-parity/M3-q4km",
        "Q5_K_M": "reports/2026-11-23-m3-q5km-parity/M3-q5km",
        "Q6_K": "reports/2026-11-23-m3-q6k-parity/M3-q6k",
    }
)
Q8_RUN = "reports/2026-11-22-m3-ckpt60-dev/grpo-m3-ckpt60-q8"


class BrowserPolicy:
    """messages -> reply text, through the bridge; any failure raises (the harness records it, RULES §4.2)."""

    def __init__(self, url: str, name: str):
        self.url, self.model_name = url, name

    def __call__(self, messages: list[dict]) -> str:
        req = urllib.request.Request(
            f"{self.url}/generate",
            json.dumps({"messages": messages}).encode(),
            {"Content-Type": "application/json"},
        )
        return json.load(urllib.request.urlopen(req, timeout=600))["text"]


def turn_stats(turns_path: Path) -> dict:
    """Per-turn wall clock (the criterion: median <= 5 s) and tok/s from the runtime's own timings."""
    rows = [json.loads(line) for line in turns_path.read_text().splitlines()]
    wall = sorted(r["wall_ms"] for r in rows)
    t = [r["timings"] for r in rows]
    pp_ms, gen_ms = sum(x["prompt_ms"] for x in t), sum(x["predicted_ms"] for x in t)
    first = [
        r["wall_ms"] for r in rows if r["n_messages"] <= 2
    ]  # system + user only: the cold prompt
    return {
        "turns": len(rows),
        "wall_ms": {
            "median": statistics.median(wall),
            "p90": wall[min(len(wall) - 1, int(len(wall) * 0.9))],
            "p99": wall[min(len(wall) - 1, int(len(wall) * 0.99))],
            "max": wall[-1],
            "mean": statistics.fmean(wall),
        },
        "prompt_tok_s": sum(x["prompt_n"] for x in t) / pp_ms * 1000 if pp_ms else None,
        "gen_tok_s": sum(x["predicted_n"] for x in t) / gen_ms * 1000 if gen_ms else None,
        "prompt_tokens_processed": sum(x["prompt_n"] for x in t),
        "prompt_tokens_cached": sum(x["cache_n"] for x in t),
        "generated_tokens": sum(x["predicted_n"] for x in t),
        "max_prompt_tokens": max(r["usage"]["prompt_tokens"] for r in rows),
        "max_total_tokens": max(r["usage"]["total_tokens"] for r in rows),
        "first_turn_wall_ms_median": statistics.median(first) if first else None,
        "finish_reasons": {k: sum(r["finish_reason"] == k for r in rows) for k in {r["finish_reason"] for r in rows}},  # fmt: skip
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quant", required=True, choices=sorted(NATIVE))
    ap.add_argument("--mode", required=True, choices=("gpu", "cpu"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ctx", type=int, default=8192)
    ap.add_argument("--bridge-port", type=int, default=8123)
    ap.add_argument(
        "--kv",
        choices=("q8_0",),
        help="KV cache type for K and V (default f16); sets flash attention on",
    )
    a = ap.parse_args()
    tag = a.quant.lower().replace("_", "")
    name = f"M3-browser-{tag}-{a.mode}" + (f"-kv{a.kv.replace('_', '')}" if a.kv else "")
    dest, bridge_dir = a.out / name, a.out / f"{name}-bridge"
    if dest.exists() or bridge_dir.exists():
        raise SystemExit(f"refusing to overwrite {dest}")
    gguf = GGUF_DIR / f"grpo-m3-ckpt60-{a.quant.lower()}.gguf"
    cfg = tomllib.loads(CFG.read_text())
    all_tasks = load_tasks("dev", "dev-eval")  # dev only
    ids = set(sample_ids(all_tasks, N, SEED))
    tasks = [t for t in all_tasks if t["id"] in ids]
    raw = ("".join(json.dumps(t) + "\n" for t in tasks)).encode()
    a.out.mkdir(parents=True, exist_ok=True)
    log_path = a.out / f"{name}-bridge.log"
    log = log_path.open("w")
    argv = ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryHigh=4G", "-p", "MemoryMax=5G",
            "node", "spikes/wllama/run.mjs", "bridge", "--model", str(gguf), "--mode", a.mode, "--ctx", str(a.ctx),
            *(["--kv-k", a.kv, "--kv-v", a.kv, "--flash-attn", "true"] if a.kv else []),
            "--bridge-port", str(a.bridge_port), "--out", str(bridge_dir.resolve()),
            "--profile", str((config.DATA_DIR / f"browser-profile-{name}").resolve())]  # fmt: skip
    proc = subprocess.Popen(argv, cwd=SITE, stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{a.bridge_port}"
    try:
        for _ in range(240):
            try:
                if urllib.request.urlopen(f"{url}/health", timeout=2).status == 200:
                    break
            except Exception:
                if proc.poll() is not None:
                    raise SystemExit(f"bridge exited early, see {log_path}") from None
                time.sleep(1)
        else:
            raise SystemExit("bridge did not come up")
        run_baseline(
            system="M3", policy=BrowserPolicy(url, name), tasks=tasks, out=dest, corpus=load_corpus(),
            meta={"model": name, "quant": a.quant, "runtime": f"wllama in Chromium ({a.mode}); see {bridge_dir.name}/env.json",
                  "temperature": 0.0, "model_config": str(CFG), "system_prompt": cfg["system_prompt"], "constrained_decoding": False,
                  "require_spec": True, "stop_after_ask": True, "parity_sample_seed": SEED, "n_ctx": a.ctx, "gguf": gguf.name, "kv_cache": a.kv or "f16"},
            tasks_sha256=hashlib.sha256(raw).hexdigest(), system_prompt_text=load_prompt(cfg["system_prompt"]),
            require_spec=True, stop_after_ask=True,
        )  # fmt: skip
    finally:
        try:
            urllib.request.urlopen(f"{url}/shutdown", timeout=30)
        except Exception:
            pass
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.terminate()  # this pid only; never `pkill -f`
        log.close()
    by_id = {t["id"]: t for t in tasks}
    new = side(dest, by_id, ids)
    summary = {"name": name, "quant": a.quant, "mode": a.mode, "this": {k: v for k, v in new.items() if k not in ("res", "eps")},
              "latency": turn_stats(bridge_dir / "turns.jsonl"), "taxonomy": {name: taxonomy(new["eps"], new["res"])}}  # fmt: skip
    for label, ref_dir in (("native_same_quant", NATIVE[a.quant]), ("native_Q8_0", Q8_RUN)):
        ref = side(Path(ref_dir), by_id, ids)
        p = parity({i: bool(r["success"]) for i, r in ref["res"].items()}, {i: bool(r["success"]) for i, r in new["res"].items()})  # fmt: skip
        tr, tn = turns(Path(ref_dir)), turns(dest)
        p["first_turn_identical"] = sum(tr[i][:1] == tn[i][:1] for i in ids) / N
        p["transcript_identical"] = sum(tr[i] == tn[i] for i in ids) / N
        summary[f"vs_{label}"] = {"ref_run": ref_dir, "ref": {k: v for k, v in ref.items() if k not in ("res", "eps")}, "parity": p}  # fmt: skip
    (a.out / f"{name}.parity.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "taxonomy"}, indent=1)[:3000])


if __name__ == "__main__":
    main()
