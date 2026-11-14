import json

import pytest

pytest.importorskip("transformers")  # train dependency group only; CI skips

from training.grpo.toy_spike import StepTimer  # noqa: E402


class State:
    def __init__(self, step):
        self.global_step = step


def test_step_timer_writes_gpu_hours_and_appends_on_resume(tmp_path, monkeypatch):
    clock = iter([0.0, 36.0, 100.0, 136.0])
    monkeypatch.setattr("training.grpo.toy_spike.time.perf_counter", lambda: next(clock))
    path = tmp_path / "toy_metrics.jsonl"
    t = StepTimer(path, n_gpus=2)
    # Real HF Trainer order: step_begin → step_end → on_log (the step's metrics arrive last).
    t.on_step_begin(None, State(0), None)
    t.on_step_end(None, State(1), None)
    t.on_log(None, State(1), None, logs={"reward": 0.25, "reward_std": 0.5})
    t.on_log(None, State(1), None, logs={"train_runtime": 1.0})  # end-of-train summary: no new row
    StepTimer(path, n_gpus=2).on_step_begin(None, State(5), None)  # resumed process appends
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    assert rows == [
        {
            "step": 1,
            "seconds": 36.0,
            "gpu_hours": 0.02,
            "n_gpus": 2,
            "mean_reward": 0.25,
            "reward_std": 0.5,
        }
    ]
