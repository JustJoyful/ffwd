"""Golden checker cases: invariants, rotation, frame counts (packages/protocol/conformance/checker-*.jsonl).

One format for all three files: {"name","inputs","spec","args","passed","failed_fields","runtimes"}. Each case
runs a real FFmpeg recipe on corpus clips and checks the output against `spec`. The TypeScript checker
(Phase 2) must produce the same pass/fail and failed fields (RULES §4.8). `runtimes` says where the RECIPE
is valid ("native" = FFmpeg 9 here; "wasm-5.1" = ffmpeg.wasm); this Python runner runs "native" cases.
"""

import json

import pytest

from training import config
from training.env.checker import check
from training.env.executor import execute, output_path_for
from training.env.probe import probe

FILES = (
    "checker-invariants.jsonl",
    "checker-rotation.jsonl",
    "checker-frames.jsonl",
    "checker-quality.jsonl",
)
CASES = [
    (f, json.loads(line))
    for f in FILES
    for line in (config.PROTOCOL_DIR / "conformance" / f).read_text().splitlines()
]


@pytest.mark.parametrize("fname,case", CASES, ids=[f"{f[8:-6]}:{c['name']}" for f, c in CASES])
def test_golden_case(fname, case, corpus, tmp_path):
    if "native" not in case["runtimes"]:
        pytest.skip(f"recipe is for {case['runtimes']}")
    run = {"action": "run", "args": case["args"], "inputs": case["inputs"], "outputs": ["out1"]}
    r = execute(
        run,
        input_paths={c: corpus[c] for c in case["inputs"]},
        output_paths={"out1": output_path_for(tmp_path, case["spec"])},
    )
    assert r.ok, r.stderr_tail
    probes = [probe(corpus[c]) for c in case["inputs"]]
    res = check(
        case["spec"],
        r.outputs["out1"],
        input_probe=probes[0],
        run_args=case["args"],
        input_probes=probes,
        input_paths=[corpus[c] for c in case["inputs"]],
    )
    failed = [c["field"] for c in res["checks"] if not c["ok"]]
    assert (res["passed"], failed) == (case["passed"], case["failed_fields"]), (
        res["measurements"],
        res["checks"],
    )
