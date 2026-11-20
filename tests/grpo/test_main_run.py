import json
from types import SimpleNamespace

import pytest

pytest.importorskip("trl")
torch = pytest.importorskip("torch")

from training.grpo import main_run  # noqa: E402


def test_refuses_to_run_without_a_gpu(monkeypatch, tmp_path):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(SystemExit, match="no CUDA"):
        main_run.main(["--init", "x", "--ckpt-dir", str(tmp_path)])


def test_main_run_only_reads_train_tasks_by_purpose():
    from training import config

    assert config.SPLIT_PURPOSES["grpo"] == ("train", "toy")


def test_stop_callback_stops_on_a_rule_and_records_why(tmp_path):
    cb = main_run.StopCallback(tmp_path, max_gpu_hours=100)
    control = SimpleNamespace(should_training_stop=False)
    cb.on_step_end(None, SimpleNamespace(global_step=3), control)
    assert control.should_training_stop is False
    cb.request("refusal_collapse")
    cb.request("something_later")  # the first reason wins
    cb.on_step_end(None, SimpleNamespace(global_step=4), control)
    assert control.should_training_stop is True
    assert json.loads((tmp_path / "stopped.json").read_text()) == {
        "step": 4,
        "reason": "refusal_collapse",
    }


def test_stop_callback_stops_when_the_stop_file_appears_and_records_it(tmp_path):
    flag = {"stop": False}
    cb = main_run.StopCallback(tmp_path, max_gpu_hours=100, stop_check=lambda: flag["stop"])
    control = SimpleNamespace(should_training_stop=False)
    cb.on_step_end(None, SimpleNamespace(global_step=7), control)
    assert control.should_training_stop is False
    flag["stop"] = True
    cb.on_step_end(None, SimpleNamespace(global_step=8), control)
    assert control.should_training_stop is True
    assert json.loads((tmp_path / "stopped.json").read_text()) == {"step": 8, "reason": "stop_file"}


def test_stop_callback_enforces_the_gpu_hour_cap(tmp_path):
    cb = main_run.StopCallback(tmp_path, max_gpu_hours=0.0)
    control = SimpleNamespace(should_training_stop=False)
    cb.on_step_end(None, SimpleNamespace(global_step=1), control)
    assert control.should_training_stop and "gpu_hour_cap" in cb.reason
