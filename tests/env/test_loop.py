import json

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


def test_finish_before_pass_rejected(tmp_path, corpus):
    policy = Scripted([FINISH, GOOD, FINISH])
    ep = run_episode(_task(), policy, corpus=corpus, job_dir=tmp_path)
    assert "finish requires a passing check" in policy.seen[1][-1]["content"]
    assert ep.end_reason == "finish" and ep.runs == 1
