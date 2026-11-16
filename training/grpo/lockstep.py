"""Batched ("lockstep") multi-turn rollouts (plan T17).

Phase 0 decoded ONE sequence at a time, so 0.071 GPU-h/step was an upper bound. Here every episode of a GRPO step runs
in its own thread; whenever all still-running episodes are waiting for the model, their prompts are decoded in ONE
batched call, then each episode continues with its own FFmpeg run. Per-episode token streams, masks and rewards are
unchanged (each episode still has its own TokenPolicy), so rollout_func returns the same structure as before.

shortcut: an episode busy in FFmpeg delays the batch until it asks again or finishes (bounded by the rollout
run timeout, 20 s); upgrade to a time-based flush if telemetry shows GPU idling.
"""

import threading
from collections.abc import Callable

BatchGenerate = Callable[[list[tuple[list[int], int]]], list[tuple[list[int], list[float]]]]


class BatchCoordinator:
    def __init__(self, generate_batch: BatchGenerate, n_episodes: int):
        self._gen, self._active = generate_batch, n_episodes
        self._cv = threading.Condition()
        self._pending: list[dict] = []
        self.batch_sizes: list[int] = []  # for telemetry and tests

    def generate(self, ids: list[int], max_new_tokens: int) -> tuple[list[int], list[float]]:
        slot: dict = {"req": (list(ids), max_new_tokens), "res": None, "err": None}
        with self._cv:
            self._pending.append(slot)
            self._flush_locked()
            while slot["res"] is None and slot["err"] is None:
                self._cv.wait()
        if slot["err"] is not None:
            raise slot["err"]
        return slot["res"]

    def episode_finished(self) -> None:
        with self._cv:
            self._active -= 1
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._pending or len(self._pending) < self._active:
            return
        batch, self._pending = self._pending, []
        self.batch_sizes.append(len(batch))
        try:
            outs = self._gen([s["req"] for s in batch])
            for s, o in zip(batch, outs, strict=True):
                s["res"] = o
        except BaseException as e:  # every waiting episode must wake and see the failure
            for s in batch:
                s["err"] = e
        self._cv.notify_all()
