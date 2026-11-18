"""Native FFmpeg 5.1.1 vs ffmpeg.wasm 5.1.4 parity over the checker conformance suite (D-024, RULES 4.8).

uv run python -m eval.runtime_parity --out reports/<date>-parity [--wasm-dir DIR]   (run under a memory cap: it starts Chromium)

Every recipe in packages/protocol/conformance/checker-*.jsonl runs (1) natively through the training executor and
(2) in ffmpeg.wasm through spikes/browser/e2e/parity-run.spec.ts (same rewriting the browser applies to model actions).
The ONE Python checker then judges both outputs with the same spec. Parity means: both runtimes succeed or fail
together, and (passed, failed fields) are identical and equal to the recorded expectation. Output probes are compared
as information (codec, size, rotation, duration), not as a verdict. The TypeScript checker does not exist yet
(Phase 2), so this tests the FFmpeg half of "what passes the checker runs in the browser" and nothing else.
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from training import config
from training.corpus.make_synthetic import ensure_corpus
from training.env.checker import check
from training.env.executor import execute, output_path_for
from training.env.ffmpeg_version import ffmpeg_version
from training.env.probe import probe

CONFORMANCE = config.PROTOCOL_DIR / "conformance"
FILES = (
    "checker-invariants.jsonl",
    "checker-rotation.jsonl",
    "checker-frames.jsonl",
    "checker-quality.jsonl",
)
OFFSET_FILE = "checker-offset.jsonl"


@dataclass
class Case:
    i: int
    name: str
    file: str
    inputs: list[str]  # clip ids; the {in:<id>} tokens in args use the same ids
    args: list[str]
    spec: dict
    passed: bool
    failed: list[str]


def load_cases() -> list[Case]:
    out: list[Case] = []
    for f in FILES:
        for line in (CONFORMANCE / f).read_text().splitlines():
            c = json.loads(line)
            out.append(
                Case(
                    len(out),
                    c["name"],
                    f,
                    c["inputs"],
                    c["args"],
                    c["spec"],
                    c["passed"],
                    c["failed_fields"],
                )
            )
    for line in (CONFORMANCE / OFFSET_FILE).read_text().splitlines():
        c = json.loads(line)
        spec = {
            "id": "out1",
            "kind": "video",
            "container": "mp4",
            "audio": {"offset_ms": c["spec_offset_ms"]},
        }
        out.append(
            Case(
                len(out),
                c["name"],
                OFFSET_FILE,
                ["clip"],
                c["args"],
                spec,
                c["passed"],
                c["failed_fields"],
            )
        )
    return out


def clip_of(case: Case, input_id: str) -> str:
    """The offset cases name their input `clip`; its corpus clip is stored in the case file."""
    if case.file != OFFSET_FILE:
        return input_id
    return next(
        json.loads(x)["clip"]
        for x in (CONFORMANCE / OFFSET_FILE).read_text().splitlines()
        if json.loads(x)["name"] == case.name
    )


def rel_out(case: Case) -> str:
    """Output path relative to the harness `out` dir: `out1.mp4` or `out1/%04d.png`."""
    with tempfile.TemporaryDirectory() as d:
        return output_path_for(Path(d), case.spec).relative_to(Path(d) / "out").as_posix()


def verdict(case: Case, out_path: Path, corpus: dict[str, Path]) -> dict:
    """Run the Python checker on one runtime's output (the dir for an image sequence)."""
    paths = [corpus[clip_of(case, i)] for i in case.inputs]
    probes = [probe(p) for p in paths]
    res = check(
        case.spec,
        out_path,
        input_probe=probes[0],
        run_args=case.args,
        input_probes=probes,
        input_paths=paths,
    )
    failed = [c["field"] for c in res["checks"] if not c["ok"]]
    p = res.get("measurements", {})
    return {
        "passed": res["passed"],
        "failed": failed,
        "measurements": {
            k: p.get(k) for k in ("duration_s", "loudness_lufs", "offset_ms", "re_encoded")
        },
    }


def run_native(case: Case, corpus: dict[str, Path], job: Path) -> dict:
    target = output_path_for(job, case.spec)
    r = execute(
        {"action": "run", "args": case.args, "inputs": case.inputs, "outputs": ["out1"]},
        input_paths={i: corpus[clip_of(case, i)] for i in case.inputs},
        output_paths={"out1": target},
    )
    if not r.ok:
        return {"ok": False, "detail": r.stderr_tail[-200:]}
    return {"ok": True} | verdict(case, r.outputs["out1"], corpus)


def run_wasm_verdict(
    case: Case, row: dict, wasm_dir: Path, corpus: dict[str, Path], job: Path
) -> dict:
    if row["code"] != 0:
        return {"ok": False, "detail": row["log_tail"][-200:]}
    target = output_path_for(job, case.spec)
    src = wasm_dir / str(case.i)
    if "%" in target.name:
        for f in (src / target.parent.name).iterdir():
            shutil.copy(f, target.parent / f.name)
        out = target.parent
    else:
        shutil.copy(src / target.name, target)
        out = target
    return {"ok": True} | verdict(case, out, corpus)


def compare(case: Case, native: dict, wasm: dict) -> list[str]:
    """Reasons this case is NOT at parity (empty = parity)."""
    why = []
    if native["ok"] != wasm["ok"]:
        why.append(
            f"exec differs: native ok={native['ok']}, wasm ok={wasm['ok']} ({wasm.get('detail') or native.get('detail')})"
        )
    elif native["ok"]:
        if (native["passed"], native["failed"]) != (wasm["passed"], wasm["failed"]):
            why.append(
                f"verdict differs: native {native['passed']} {native['failed']}, wasm {wasm['passed']} {wasm['failed']}"
            )
        if (native["passed"], native["failed"]) != (case.passed, case.failed):
            why.append(f"native differs from the recorded expectation {case.passed} {case.failed}")
    return why


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out", type=Path, required=True, help="fresh report directory (never overwritten)"
    )
    ap.add_argument(
        "--keep-work", action="store_true", help="keep the scratch outputs (about 600 MB)"
    )
    ap.add_argument("--wasm-dir", type=Path, help="reuse the outputs of an earlier browser run")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    cases = load_cases()
    work = Path(os.environ.get("PARITY_WORK", Path.home() / ".cache" / "ffmpeg-agent" / "parity"))
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    corpus = ensure_corpus(config.CORPUS_DIR)
    wasm_dir = a.wasm_dir or work / "wasm"
    if a.wasm_dir is None:
        spec_cases = [
            {
                "i": c.i,
                "name": c.name,
                "inputs": {i: corpus[clip_of(c, i)].name for i in c.inputs},
                "args": c.args,
                "out": rel_out(c),
            }
            for c in cases
        ]
        (work / "cases.json").write_text(json.dumps(spec_cases))
        env = os.environ | {"PARITY_CASES": str(work / "cases.json"), "PARITY_OUT": str(wasm_dir)}
        subprocess.run(
            ["pnpm", "exec", "playwright", "test", "e2e/parity-run.spec.ts", "--reporter=line"],
            cwd=config.REPO_ROOT / "spikes" / "browser", env=env, check=True,
        )  # fmt: skip
    wasm_rows = {r["i"]: r for r in json.loads((wasm_dir / "results.json").read_text())}
    rows = []
    for c in cases:
        native = run_native(c, corpus, work / f"n{c.i}")
        wasm = run_wasm_verdict(c, wasm_rows[c.i], wasm_dir, corpus, work / f"w{c.i}")
        rows.append(
            {
                "i": c.i,
                "file": c.file,
                "name": c.name,
                "expected": [c.passed, c.failed],
                "native": native,
                "wasm": wasm,
                "not_parity": compare(c, native, wasm),
            }
        )
        print(("PARITY " if not rows[-1]["not_parity"] else "DIFF   ") + c.name, flush=True)
    bad = [r for r in rows if r["not_parity"]]
    (a.out / "results.json").write_text(json.dumps(rows, indent=1) + "\n")
    (a.out / "manifest.json").write_text(json.dumps({
        "native_ffmpeg": ffmpeg_version(config.FFMPEG_BIN), "wasm": "ffmpeg.wasm core-mt 0.12.10 (FFmpeg 5.1.4)",
        "cases": len(rows), "parity": len(rows) - len(bad), "not_parity": len(bad), "paid_cost_usd": 0.0,
    }, indent=1) + "\n")  # fmt: skip
    print(f"{len(rows) - len(bad)}/{len(rows)} cases at parity")
    if not a.keep_work:
        shutil.rmtree(
            work, ignore_errors=True
        )  # ~600 MB of outputs; the verdicts are in results.json


if __name__ == "__main__":
    main()
