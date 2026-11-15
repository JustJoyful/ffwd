import re

from jsonschema import Draft202012Validator

from training import config
from training.env.constrained import action_json_schema, load_prompt
from training.env.loop import initial_messages, run_episode
from training.protocol import validate

RUN = {
    "action": "run",
    "args": ["-i", "{in:clip}", "{out:out1}"],
    "inputs": ["clip"],
    "outputs": ["out1"],
}


def test_schema_accepts_protocol_actions_and_rejects_junk():
    v = Draft202012Validator(action_json_schema())
    for a in (
        RUN,
        {"action": "finish", "outputs": ["out1"], "note": "done"},
        {"action": "ask_user", "question": "Which part?"},
        {"action": "unsupported", "reason": "object removal"},
    ):
        assert v.is_valid(a), a
        assert validate("action", a) == [], a  # the constrained schema is a subset of the protocol
    for bad in (
        {"action": "shell"},
        {"action": "run", "args": "x", "inputs": [], "outputs": ["o"]},
        {"action": "run"},
        {"args": []},
    ):
        assert not v.is_valid(bad), bad


def test_spec_is_not_offered_to_small_models():
    # The fair prompt skips `spec`: it is not needed to run or be graded, and base models copied its example.
    assert "spec" not in action_json_schema()["oneOf"][0]["properties"]["action"].get("enum", [])
    assert not Draft202012Validator(action_json_schema()).is_valid({"action": "spec", "spec": {}})


def test_small_model_prompt_has_no_copyable_actions():
    text = load_prompt("system-v0-small.txt")
    assert not re.search(r'\{\s*"action"', text), "a concrete example action would be copyable"
    assert "{in:" in text and "{out:" in text  # the file-id grammar is still explained
    for word in ("run", "finish", "ask_user", "unsupported"):
        assert word in text


def test_run_episode_uses_a_custom_system_prompt(corpus, tmp_path):
    task = {
        "id": "t",
        "split": "dev",
        "source": "x",
        "request": "r",
        "inputs": ["clip_a"],
        "gold_spec": None,
        "families": ["F1"],
        "difficulty": 1,
        "flags": {"ambiguous": False, "unsupported": True},
        "clarification": None,
        "reference_runs": None,
    }
    seen = []

    def policy(messages):
        seen.append(messages)
        return '{"action": "unsupported", "reason": "x"}'

    run_episode(
        task, policy, corpus=corpus, job_dir=tmp_path, system_prompt_text="CUSTOM SYSTEM PROMPT"
    )
    assert seen[0][0] == {"role": "system", "content": "CUSTOM SYSTEM PROMPT"}
    # default is unchanged
    assert initial_messages(task, {"clip_a": {}})[0]["content"].startswith("You are ffmpeg-agent")


def test_constrained_policy_sends_response_format(monkeypatch):
    from training.policies import ChatPolicy

    p = ChatPolicy("http://x", "m", None, max_tokens=8, response_format={"type": "json_schema"})
    assert p.extra_body == {"response_format": {"type": "json_schema"}}
    p2 = ChatPolicy(
        "http://x",
        "m",
        None,
        max_tokens=8,
        extra_body={"a": 1},
        response_format={"type": "json_object"},
    )
    assert p2.extra_body == {"a": 1, "response_format": {"type": "json_object"}}


def test_fair_configs_exist_and_are_wired():
    import tomllib

    for size in ("0.6b", "1.7b"):
        cfg = tomllib.loads(
            (config.REPO_ROOT / "eval" / "configs" / f"qwen3-{size}-fair.toml").read_text()
        )
        assert (
            cfg["model"] == f"qwen3-{size}-fair"
            and cfg["system_prompt"] == "system-v0-small.txt"
            and cfg["constrained"] is True
        )
