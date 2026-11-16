import json
import threading
import time

import pytest
from test_rollout import FINISH, GOOD, IM_END, TASK, FakeTok  # noqa: F401

from training.grpo.lockstep import BatchCoordinator
from training.grpo.rollout import make_rollout_func, prompt_messages
from training.taskgen.toy import make_toy_tasks


def _run_threads(coord, n, replies_per_thread):
    results = [None] * n

    def worker(i):
        got = []
        try:
            for r in range(replies_per_thread[i]):
                got.append(coord.generate([i, r], 4))
        finally:
            coord.episode_finished()
        results[i] = got

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    [t.start() for t in threads]
    [t.join(10) for t in threads]
    return results


def test_all_waiting_episodes_are_decoded_in_one_batch():
    seen = []

    def gen(reqs):
        seen.append(len(reqs))
        return [([ids[0], ids[1]], [0.0, 0.0]) for ids, _ in reqs]

    coord = BatchCoordinator(gen, 4)
    out = _run_threads(coord, 4, [2, 2, 2, 2])
    assert seen == [4, 4] and out[3] == [([3, 0], [0.0, 0.0]), ([3, 1], [0.0, 0.0])]


def test_a_finished_episode_leaves_the_quorum():
    seen = []

    def gen(reqs):
        seen.append(len(reqs))
        return [([1], [0.0])] * len(reqs)

    coord = BatchCoordinator(gen, 3)
    _run_threads(coord, 3, [1, 3, 3])  # one episode ends after a single turn
    assert seen[0] == 3 and 3 not in seen[1:] and sum(seen) == 7


def test_generation_errors_reach_every_waiting_episode():
    def boom(reqs):
        raise RuntimeError("cuda oom")

    coord = BatchCoordinator(boom, 2)
    errors = []

    def worker():
        try:
            coord.generate([1], 4)
        except RuntimeError as e:
            errors.append(str(e))
        finally:
            coord.episode_finished()

    ts = [threading.Thread(target=worker) for _ in range(2)]
    [t.start() for t in ts]
    [t.join(10) for t in ts]
    assert errors == ["cuda oom", "cuda oom"]


class ScriptedBatch:
    """Replies keyed by how many assistant turns the prompt already contains (stateless, so order-independent)."""

    def __init__(self, replies):
        self.replies, self.batch_sizes = replies, []

    def __call__(self, reqs):
        self.batch_sizes.append(len(reqs))
        out = []
        for ids, _ in reqs:
            turn = (
                FakeTok().decode(ids).count("<assistant>") - 1
            )  # one generation prompt per turn, plus history
            text = self.replies[min(turn, len(self.replies) - 1)]
            toks = FakeTok().encode(text) + [IM_END]
            out.append((toks, [-0.25] * len(toks)))
        return out


def test_lockstep_rollout_matches_sequential_structure_and_rewards(corpus, tmp_path):
    trainer = type("T", (), {"processing_class": FakeTok()})()
    prompt = prompt_messages(TASK, corpus)
    batch = ScriptedBatch([GOOD, FINISH])
    rollout = make_rollout_func(
        [TASK],
        corpus,
        None,
        jobs_root=tmp_path,
        max_new_tokens=64,
        batch_generator_for=lambda tr: batch,
    )
    out = rollout([prompt] * 3, trainer)
    assert len(out["completion_ids"]) == 3 and out["toy_reward"] == [1.0, 1.0, 1.0]
    assert batch.batch_sizes[0] == 3  # first turn of all three episodes decoded together
    for ids, mask, lps in zip(out["completion_ids"], out["env_mask"], out["logprobs"], strict=True):
        assert (
            len(ids) == len(mask) == len(lps) and mask[0] == 1 and 0 in mask
        )  # observations are masked


def test_run_timeout_of_one_episode_does_not_stall_the_batch(corpus, tmp_path):
    slow = make_toy_tasks(1, seed=9)[0]
    trainer = type("T", (), {"processing_class": FakeTok()})()
    batch = ScriptedBatch([GOOD, FINISH])
    t0 = time.time()
    rollout = make_rollout_func(
        [TASK, slow],
        corpus,
        None,
        jobs_root=tmp_path,
        max_new_tokens=64,
        batch_generator_for=lambda tr: batch,
    )
    rollout([prompt_messages(TASK, corpus), prompt_messages(slow, corpus)], trainer)
    assert time.time() - t0 < 60


def test_unknown_prompt_still_raises_in_lockstep_mode(corpus, tmp_path):
    rollout = make_rollout_func(
        [TASK],
        corpus,
        None,
        jobs_root=tmp_path,
        max_new_tokens=8,
        batch_generator_for=lambda tr: ScriptedBatch(["x"]),
    )
    trainer = type("T", (), {"processing_class": FakeTok()})()
    with pytest.raises(KeyError):
        rollout([[{"role": "user", "content": json.dumps("nope")}]], trainer)
