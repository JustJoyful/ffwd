import json

import pytest

from training import config
from training.env.validator import uses_stream_copy_only, validate_run

CASES = [
    json.loads(line)
    for line in (config.PROTOCOL_DIR / "conformance" / "validator.jsonl").read_text().splitlines()
]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_conformance_cases(case):
    r = validate_run(
        case["args"],
        case["inputs"],
        case["outputs"],
        known_inputs=set(case["inputs"]),
        known_outputs=set(case["outputs"]),
    )
    assert r.ok == case["ok"], r.reason
    if not case["ok"]:
        assert case["reason_contains"] in r.reason


def test_unknown_output_id_rejected_even_if_declared():
    r = validate_run(
        ["-i", "{in:a}", "{out:x}"], ["a"], ["x"], known_inputs={"a"}, known_outputs={"y"}
    )
    assert not r.ok and "unknown id: x" in r.reason


def test_stream_copy_only_detection():
    assert uses_stream_copy_only(["-c", "copy"])
    assert uses_stream_copy_only(["-c:v", "copy", "-c:a", "copy", "-an"])
    assert not uses_stream_copy_only(["-c:v", "copy", "-vf", "scale=640:-2"])
    assert not uses_stream_copy_only(["-c:v", "copy", "-c:a", "aac"])
    assert not uses_stream_copy_only(["-ss", "2"])  # no codec option → FFmpeg re-encodes by default


def test_non_ascii_digits_rejected():
    # Python's \d matches Arabic-Indic digits; the JS validator is ASCII-only, so ours must be too.
    r = validate_run(
        ["-i", "{in:a}", "-t", "١٢", "{out:o}"],
        ["a"],
        ["o"],
        known_inputs={"a"},
        known_outputs={"o"},
    )
    assert not r.ok
