import json

import pytest

from training import config
from training.env.describe_spec import describe_spec

GOLDEN = [
    json.loads(x)
    for x in (config.PROTOCOL_DIR / "conformance" / "describe-spec.jsonl").read_text().splitlines()
]


@pytest.mark.parametrize("case", GOLDEN, ids=[c["name"] for c in GOLDEN])
def test_describe_matches_golden(case):
    assert describe_spec(case["spec"]) == case["lines"]


def test_unconstrained_fields_are_not_mentioned():
    spec = {
        "family": ["F1"],
        "outputs": [
            {
                "id": "out1",
                "kind": "video",
                "container": None,
                "video": {"width": None, "codec": None},
                "audio": None,
                "time": {"start_s": None, "end_s": None, "tolerance_s": 0.1},
            }
        ],
    }
    assert describe_spec(spec) == ["Result: a video"]


def test_every_gold_spec_in_spike_v1_has_a_description():
    for line in (config.DATA_DIR / "tasks" / "dev" / "spike-v1.jsonl").read_text().splitlines():
        t = json.loads(line)
        if t["gold_spec"]:
            lines = describe_spec(t["gold_spec"])
            assert lines and all(isinstance(x, str) and x for x in lines), t["id"]


def test_multiple_outputs_are_numbered():
    spec = {
        "family": ["F7"],
        "outputs": [{"id": "a", "kind": "video"}, {"id": "b", "kind": "audio", "container": "mp3"}],
    }
    assert describe_spec(spec) == [
        "Output 1:",
        "  Result: a video",
        "Output 2:",
        "  Result: an audio file (MP3)",
    ]
