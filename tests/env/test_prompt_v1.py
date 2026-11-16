import hashlib
import json

from training import config
from training.env.loop import initial_messages

PROMPT = (config.PROTOCOL_DIR / "prompts" / config.SYSTEM_PROMPT_V1).read_text()
SPEC = json.loads((config.PROTOCOL_DIR / "schemas" / "spec.schema.json").read_text())


def test_prompt_documents_every_action_and_the_spec_first_rule():
    for action in ("spec", "run", "finish", "ask_user", "unsupported"):
        assert f'"{action}"' in PROMPT, action
    assert "FIRST action must be a spec" in PROMPT


def test_prompt_names_every_spec_field_so_it_cannot_drift_from_the_schema():
    out = SPEC["$defs"]["output"]["properties"]
    names = set(out)
    for section in ("video", "audio", "time", "frames", "quality"):
        names |= set(out[section]["properties"])
    missing = sorted(n for n in names if n not in PROMPT and n not in {"id", "per_input"})
    assert missing == []


def test_prompt_is_short_enough_for_a_small_model():
    assert (
        len(PROMPT.split()) < 900
    )  # ~1.3k tokens; the 4k context budget also holds the probe and observations


def test_prompt_has_no_copyable_example_actions():
    assert '{"action"' not in PROMPT  # Phase 0: small models copy example JSON literally


def test_frozen_hash_matches_when_pinned():
    if config.SYSTEM_PROMPT_V1_SHA256 is not None:
        assert hashlib.sha256(PROMPT.encode()).hexdigest() == config.SYSTEM_PROMPT_V1_SHA256


def test_v1_prompt_can_be_injected_into_the_first_message():
    task = {"request": "r", "inputs": ["c"], "gold_spec": {"outputs": [{"id": "out1"}]}}
    msgs = initial_messages(task, {"c": {"duration_s": 1}}, PROMPT)
    assert msgs[0]["content"] == PROMPT
