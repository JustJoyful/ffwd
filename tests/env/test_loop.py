import json

import pytest

from training.env.loop import run_episode, score

TRIM_GOLD = {
    "family": ["F1"],
    "outputs": [
        {
            "id": "out1",
            "kind": "video",
            "container": "mp4",
            "time": {"start_s": 2, "end_s": 5, "tolerance_s": 0.1},
        }
    ],
}


def _task(gold=TRIM_GOLD, ambiguous=False, unsupported=False):
    return {
        "id": "t-trim",
        "split": "dev",
        "source": "test",
        "request": "keep 0:02 to 0:05",
        "inputs": ["h264_long"],
        "gold_spec": gold,
        "families": ["F1"],
        "difficulty": 1,
        "flags": {"ambiguous": ambiguous, "unsupported": unsupported},
        "clarification": None,
        "reference_runs": None,
    }


def _run(args):
    return json.dumps({"action": "run", "args": args, "inputs": ["h264_long"], "outputs": ["out1"]})


GOOD = _run(["-ss", "2", "-i", "{in:h264_long}", "-t", "3", "-c", "copy", "{out:out1}"])
BAD = _run(["-ss", "2", "-i", "{in:h264_long}", "-t", "9", "-c", "copy", "{out:out1}"])
FINISH = json.dumps({"action": "finish", "outputs": ["out1"], "note": "done"})
SPEC = json.dumps({"action": "spec", "spec": TRIM_GOLD})


class Scripted:
    def __init__(self, replies):
        self.replies, self.seen = list(replies), []

    def __call__(self, messages):
        self.seen.append(list(messages))
        return self.replies.pop(0)


def test_pass_trim_episode(tmp_path, corpus):
    ep = run_episode(_task(), Scripted([SPEC, GOOD, FINISH]), corpus=corpus, job_dir=tmp_path)
    assert ep.end_reason == "finish" and ep.runs == 1 and ep.emitted_spec == TRIM_GOLD
    assert score(_task(), ep)


def test_first_message_has_probe_but_no_paths(tmp_path, corpus):
    policy = Scripted([GOOD, FINISH])
    run_episode(_task(), policy, corpus=corpus, job_dir=tmp_path)
    system, user = policy.seen[0]
    assert system["role"] == "system" and "{in:" in system["content"]
    assert "duration_s" in user["content"] and str(tmp_path) not in user["content"]
    assert str(corpus["h264_long"].parent) not in user["content"]


def test_invalid_then_recover(tmp_path, corpus):
    ep = run_episode(
        _task(), Scripted(["ffmpeg -i x y", GOOD, FINISH]), corpus=corpus, job_dir=tmp_path
    )
    assert ep.invalid_turns == 1 and score(_task(), ep)


def test_failed_check_feeds_back_then_retry(tmp_path, corpus):
    policy = Scripted([BAD, GOOD, FINISH])
    ep = run_episode(_task(), policy, corpus=corpus, job_dir=tmp_path)
    obs = json.loads(policy.seen[1][-1]["content"])
    assert obs["checks"]["out1"]["passed"] is False
    assert ep.runs == 2 and score(_task(), ep)


def test_run_budget_exhausted_scores_false(tmp_path, corpus):
    ep = run_episode(_task(), Scripted([BAD] * 5), corpus=corpus, job_dir=tmp_path, max_runs=2)
    assert ep.end_reason == "run_budget" and ep.runs == 2
    assert not score(_task(), ep)


def test_turn_budget_ends_episode(tmp_path, corpus):
    ep = run_episode(_task(), Scripted(["nope"] * 20), corpus=corpus, job_dir=tmp_path)
    assert ep.end_reason == "turn_budget" and not score(_task(), ep)


def test_ambiguous_scored_by_ask(tmp_path, corpus):
    t = _task(gold=None, ambiguous=True)
    ask = json.dumps({"action": "ask_user", "question": "Which part should I keep?"})
    ep = run_episode(
        t,
        Scripted([ask, json.dumps({"action": "unsupported", "reason": "x"})]),
        corpus=corpus,
        job_dir=tmp_path,
    )
    assert ep.asked and score(t, ep)
    ep2 = run_episode(
        t, Scripted([GOOD, FINISH] + ["x"] * 8), corpus=corpus, job_dir=tmp_path / "b"
    )
    assert not score(t, ep2)


def test_second_ask_is_invalid(tmp_path, corpus):
    ask = json.dumps({"action": "ask_user", "question": "Which part?"})
    ep = run_episode(_task(), Scripted([ask, ask, GOOD, FINISH]), corpus=corpus, job_dir=tmp_path)
    assert ep.invalid_turns == 1 and score(_task(), ep)


def test_unsupported_scored_without_runs(tmp_path, corpus):
    t = _task(gold=None, unsupported=True)
    refuse = json.dumps(
        {"action": "unsupported", "reason": "object removal", "nearest_supported": None}
    )
    ep = run_episode(t, Scripted([refuse]), corpus=corpus, job_dir=tmp_path)
    assert ep.refused and ep.end_reason == "unsupported" and score(t, ep)
    assert not score(_task(), ep)  # refusing a supported task is a failure


@pytest.mark.parametrize("nearest", [None, "F4", "F9", "F12"])
def test_unsupported_score_and_reward_ignore_nearest_supported(tmp_path, corpus, nearest):
    """Owner decision 20 Nov 2026: only the `unsupported` action is graded; the label is descriptive."""
    from training import config
    from training.grpo.telemetry import grpo_reward

    t = _task(gold=None, unsupported=True)
    refuse = json.dumps({"action": "unsupported", "reason": "x", "nearest_supported": nearest})
    ep = run_episode(t, Scripted([refuse]), corpus=corpus, job_dir=tmp_path)
    assert score(t, ep) and ep.invalid_turns == 0
    assert grpo_reward(t, ep).terms["clarify"] == 1.0
    assert config.REWARD_SCORES_NEAREST_SUPPORTED is False


def test_finish_before_pass_rejected(tmp_path, corpus):
    policy = Scripted([FINISH, GOOD, FINISH])
    ep = run_episode(_task(), policy, corpus=corpus, job_dir=tmp_path)
    assert "finish requires a passing check" in policy.seen[1][-1]["content"]
    assert ep.end_reason == "finish" and ep.runs == 1


def test_require_spec_rejects_a_run_before_any_spec(corpus, tmp_path):
    policy = Scripted([GOOD, SPEC, GOOD, FINISH])
    ep = run_episode(_task(), policy, corpus=corpus, job_dir=tmp_path, require_spec=True)
    assert (
        ep.invalid_turns == 1 and ep.runs == 1
    )  # the early run was rejected and NOT counted as a run
    assert "spec action first" in ep.turns[0]["observation"]["error"]
    assert ep.emitted_spec == TRIM_GOLD and score(_task(), ep)


def test_require_spec_off_by_default_keeps_phase0_behaviour(corpus, tmp_path):
    ep = run_episode(_task(), Scripted([GOOD, FINISH]), corpus=corpus, job_dir=tmp_path)
    assert ep.invalid_turns == 0 and score(_task(), ep)


def test_ask_user_and_unsupported_are_allowed_before_a_spec(corpus, tmp_path):
    task = _task(gold=None, unsupported=True)
    reply = json.dumps({"action": "unsupported", "reason": "no", "nearest_supported": None})
    ep = run_episode(task, Scripted([reply]), corpus=corpus, job_dir=tmp_path, require_spec=True)
    assert ep.refused and ep.invalid_turns == 0


def test_stop_after_ask_ends_an_ambiguous_episode_and_still_scores(corpus, tmp_path):
    task = _task(gold=None, ambiguous=True) | {"clarification": "keep the first 10 seconds"}
    ask = json.dumps({"action": "ask_user", "question": "how long?"})
    stopped = run_episode(
        task, Scripted([ask]), corpus=corpus, job_dir=tmp_path / "a", stop_after_ask=True
    )
    assert stopped.end_reason == "asked" and len(stopped.turns) == 1 and score(task, stopped)
    assert stopped.turns[0]["observation"] == {"answer": "keep the first 10 seconds"}
    flailing = run_episode(
        task,
        Scripted([ask] + [FINISH] * 8),
        corpus=corpus,
        job_dir=tmp_path / "b",
        stop_after_ask=False,
    )
    assert len(flailing.turns) == 8 and score(
        task, flailing
    )  # Phase 0 behaviour: runs on until the turn cap
