import pytest

from training.grpo.hf_batch import run_chunks


class FakeOOM(Exception):
    pass


def is_oom(e):
    return isinstance(e, FakeOOM)


def reqs(n):
    return [([i], 4) for i in range(n)]


def test_chunks_are_at_most_max_batch_and_order_is_preserved():
    seen = []

    def one(chunk):
        seen.append(len(chunk))
        return [(ids, [0.0]) for ids, _ in chunk]

    out = run_chunks(reqs(20), one, max_batch=8, is_oom=is_oom)
    assert seen == [8, 8, 4] and [o[0][0] for o in out] == list(range(20))


def test_an_oom_splits_the_chunk_in_half_retries_and_keeps_order():
    seen, emptied = [], []

    def one(chunk):
        seen.append(len(chunk))
        if len(chunk) > 2:
            raise FakeOOM("CUDA out of memory")
        return [(ids, [0.0]) for ids, _ in chunk]

    out = run_chunks(reqs(8), one, max_batch=8, is_oom=is_oom, on_oom=lambda: emptied.append(1))
    assert [o[0][0] for o in out] == list(range(8))
    assert seen == [8, 4, 2, 2, 4, 2, 2] and len(emptied) == 3  # 8 -> 4+4 -> 2+2 each


def test_a_single_request_that_still_does_not_fit_raises_and_other_errors_are_not_swallowed():
    def always_oom(chunk):
        raise FakeOOM("no")

    with pytest.raises(FakeOOM):
        run_chunks(reqs(2), always_oom, max_batch=8, is_oom=is_oom)

    def bug(chunk):
        raise ValueError("not an oom")

    with pytest.raises(ValueError):
        run_chunks(reqs(4), bug, max_batch=8, is_oom=is_oom)
