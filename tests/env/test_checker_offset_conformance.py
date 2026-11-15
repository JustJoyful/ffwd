"""Golden A/V-offset cases (packages/protocol/conformance/checker-offset.jsonl).

Each case runs a real FFmpeg recipe on a corpus clip and checks the output against an offset spec.
The TypeScript checker (Phase 2) must produce the same pass/fail and failed fields (RULES §4.8).
"""

import json

import pytest

from training import config
from training.env.checker import check
from training.env.executor import execute, output_path_for
from training.env.probe import probe

CASES = [
    json.loads(line)
    for line in (config.PROTOCOL_DIR / "conformance" / "checker-offset.jsonl")
    .read_text()
    .splitlines()
]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_offset_golden_case(case, corpus, tmp_path):
    spec = {
        "id": "out1",
        "kind": "video",
        "container": "mp4",
        "audio": {"offset_ms": case["spec_offset_ms"]},
    }
    run = {"action": "run", "args": case["args"], "inputs": ["clip"], "outputs": ["out1"]}
    r = execute(
        run,
        input_paths={"clip": corpus[case["clip"]]},
        output_paths={"out1": output_path_for(tmp_path, spec)},
    )
    assert r.ok, r.stderr_tail
    res = check(
        spec, r.outputs["out1"], input_probe=probe(corpus[case["clip"]]), run_args=case["args"]
    )
    failed = [c["field"] for c in res["checks"] if not c["ok"]]
    assert (res["passed"], failed) == (case["passed"], case["failed_fields"]), res["measurements"]
