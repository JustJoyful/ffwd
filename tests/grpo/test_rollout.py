import json

import pytest

from training import config
from training.env.loop import run_episode
from training.grpo.rollout import TokenPolicy, make_rollout_func, prompt_messages, toy_reward
from training.taskgen.toy import make_toy_tasks

IM_END = 100_000


class FakeTok:
    """Char-level stand-in for a HF tokenizer with a ChatML template."""

    def encode(self, text, add_special_tokens=False):
        return [ord(c) for c in text]

    def decode(self, ids, skip_special_tokens=True):
        return "".join(chr(i) for i in ids if i != IM_END)

    def convert_tokens_to_ids(self, tok):
        assert tok == "<|im_end|>"
        return IM_END

    def apply_chat_template(self, messages, add_generation_prompt, enable_thinking, tokenize):
        assert tokenize and add_generation_prompt and enable_thinking is False
        text = "".join(f"<{m['role']}>{m['content']}" for m in messages) + "<assistant>"
        return self.encode(text)


class FakeGen:
    def __init__(self, replies, end=True):
        self.replies, self.end, self.calls = list(replies), end, []

    def __call__(self, ids, max_new_tokens):
        self.calls.append(list(ids))
        out = FakeTok().encode(self.replies.pop(0)) + ([IM_END] if self.end else [])
        return out, [-0.25] * len(out)


TASK = make_toy_tasks(1, seed=3)[0]
GOOD = json.dumps(TASK["reference_runs"][0])
FINISH = json.dumps({"action": "finish", "outputs": ["out1"], "note": "ok"})


def test_token_stream_masks_observations(corpus, tmp_path):
    tok, gen = FakeTok(), FakeGen([GOOD, FINISH])
    pol = TokenPolicy(tok, gen, max_new_tokens=64)
    ep = run_episode(TASK, pol, corpus=corpus, job_dir=tmp_path)
    assert ep.end_reason == "finish"
    t = pol.trajectory()
    assert t["prompt_ids"] == tok.apply_chat_template(
        prompt_messages(TASK, corpus),
        add_generation_prompt=True,
        enable_thinking=False,
        tokenize=True,
    )
    n1 = len(GOOD) + 1
    assert t["env_mask"][:n1] == [1] * n1 and t["logprobs"][:n1] == [-0.25] * n1
    obs_len = len(t["completion_ids"]) - n1 - (len(FINISH) + 1)
    assert obs_len > 0 and t["env_mask"][n1 : n1 + obs_len] == [0] * obs_len
    assert t["logprobs"][n1 : n1 + obs_len] == [0.0] * obs_len
    assert len(t["completion_ids"]) == len(t["env_mask"]) == len(t["logprobs"])
    # the 2nd generation is conditioned on exactly prompt + completion-so-far (one token stream)
    assert gen.calls[1] == t["prompt_ids"] + t["completion_ids"][: n1 + obs_len]
    obs_text = FakeTok().decode(t["completion_ids"][n1 : n1 + obs_len])
    assert obs_text.startswith("\n<|im_start|>user\n") and '"run_ok": true' in obs_text


def test_truncated_generation_gets_masked_im_end(corpus, tmp_path):
    pol = TokenPolicy(FakeTok(), FakeGen(["garbage", "garbage"], end=False), max_new_tokens=8)
    pol([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}])
    pol(
        [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "garbage"},
            {"role": "user", "content": "{}"},
        ]
    )
    t = pol.trajectory()
    i = len("garbage")
    assert t["completion_ids"][i] == IM_END and t["env_mask"][i] == 0


def test_toy_reward():
    from training.env.loop import Episode

    ok = Episode(task_id="x", last_check={"passed": True}, invalid_turns=1)
    assert toy_reward(TASK, ok) == pytest.approx(0.5)
    assert toy_reward(TASK, Episode(task_id="x")) == 0.0


def test_rollout_func_assembles_one_completion_per_prompt(corpus, tmp_path):
    trainer = type("T", (), {"processing_class": FakeTok()})()
    replies = [GOOD, FINISH, "nope", "nope", "nope", "nope", "nope", "nope", "nope", "nope"]
    gen = FakeGen(replies)
    rollout = make_rollout_func(
        [TASK], corpus, lambda tr: gen, jobs_root=tmp_path, max_new_tokens=64
    )
    prompt = prompt_messages(TASK, corpus)
    out = rollout([prompt, prompt], trainer)
    assert set(out) >= {"prompt_ids", "completion_ids", "logprobs", "env_mask", "toy_reward"}
    assert len(out["completion_ids"]) == 2
    assert out["toy_reward"] == [1.0, pytest.approx(-0.5 * config.MAX_TURNS_PER_JOB)]


def test_unknown_prompt_raises(corpus, tmp_path):
    rollout = make_rollout_func(
        [TASK], corpus, lambda tr: FakeGen([]), jobs_root=tmp_path, max_new_tokens=8
    )
    trainer = type("T", (), {"processing_class": FakeTok()})()
    with pytest.raises(KeyError):
        rollout([[{"role": "user", "content": "not a task"}]], trainer)


class DictTok(FakeTok):
    """transformers 5 returns a BatchEncoding (dict-like) from apply_chat_template(tokenize=True)."""

    def apply_chat_template(self, *a, **k):
        return {"input_ids": super().apply_chat_template(*a, **k), "attention_mask": [1]}


def test_prompt_ids_from_batch_encoding():
    pol = TokenPolicy(DictTok(), FakeGen(["x"]), max_new_tokens=8)
    pol([{"role": "user", "content": "u"}])
    assert all(isinstance(i, int) for i in pol.trajectory()["prompt_ids"])


def _scripted_rollout(corpus, tmp_path, **kw):
    trainer = type(
        "T", (), {"processing_class": FakeTok(), "state": type("S", (), {"global_step": 4})()}
    )()
    gen = FakeGen([GOOD, FINISH] + ["nope"] * 40)
    rollout = make_rollout_func(
        [TASK], corpus, lambda tr: gen, jobs_root=tmp_path, max_new_tokens=64, **kw
    )
    prompt = prompt_messages(TASK, corpus)
    return rollout([prompt, prompt, prompt], trainer)


def test_on_rollout_receives_the_step_records_and_transcripts(corpus, tmp_path):
    from training.grpo.telemetry import grpo_reward

    seen = []
    out = _scripted_rollout(
        corpus, tmp_path, reward_fn=grpo_reward, on_rollout=lambda *a: seen.append(a)
    )
    step, records, episodes = seen[0]
    assert step == 5  # trainer.state.global_step + 1: the optimizer step this rollout feeds
    assert len(records) == len(episodes) == 3 == len(out["reward"])
    assert {r["group"] for r in records} == {
        f"5:{TASK['id']}"
    }  # the 3 rollouts of one prompt form one group
    assert records[0]["passed"] is True and records[0]["total"] == pytest.approx(out["reward"][0])
    assert episodes[0]["task_id"] == TASK["id"] and "turns" in episodes[0]


def test_shuffle_control_changes_trained_rewards_but_logs_true_ones(corpus, tmp_path):
    from training.grpo.telemetry import grpo_reward

    seen = []
    plain = _scripted_rollout(corpus, tmp_path / "a", reward_fn=grpo_reward)
    ctrl = _scripted_rollout(
        corpus,
        tmp_path / "b",
        reward_fn=grpo_reward,
        shuffle_seed=3,
        on_rollout=lambda *a: seen.append(a),
    )
    assert sorted(ctrl["reward"]) == sorted(plain["reward"])  # same multiset within the group
    true_totals = [r["total"] for r in seen[0][1]]
    assert true_totals == plain["reward"]  # telemetry always logs the TRUE reward
