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


def test_refuses_to_train_without_gpu(tmp_path, monkeypatch):
    # An unattended Kaggle run must not silently fall back to CPU and burn the quota for hours.
    import training.grpo.toy_spike as ts

    monkeypatch.setattr(ts.torch.cuda, "is_available", lambda: False)
    with pytest.raises(SystemExit, match="no CUDA GPU"):
        ts.main(["--steps", "1", "--ckpt-dir", str(tmp_path)])


def test_precision_plan_for_t4_and_ampere():
    import torch

    from training.grpo.toy_spike import precision_plan

    t4 = precision_plan("auto", bf16_supported=False)  # Tesla T4, compute capability 7.5
    assert t4 == {
        "bf16": False,
        "fp16": True,
        "model_dtype": torch.float16,
        "mixed_out_gemm": False,
    }
    amp = precision_plan("auto", bf16_supported=True)
    assert amp == {
        "bf16": True,
        "fp16": False,
        "model_dtype": torch.bfloat16,
        "mixed_out_gemm": True,
    }
    assert precision_plan("fp16", bf16_supported=True) == t4  # lets us test the T4 path on Ampere


def test_native_bf16_uses_compute_capability_not_emulation(monkeypatch):
    # torch.cuda.is_bf16_supported() counts emulation and returns True on a T4 (crashed on Kaggle).
    import torch

    from training.grpo.toy_spike import native_bf16

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda *a, **k: True)
    monkeypatch.setattr(torch.cuda, "get_device_capability", lambda *a: (7, 5))  # Tesla T4
    assert native_bf16() is False
    monkeypatch.setattr(torch.cuda, "get_device_capability", lambda *a: (8, 6))  # RTX 3050
    assert native_bf16() is True
