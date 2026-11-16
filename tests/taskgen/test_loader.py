import json

import pytest

from training import config
from training.protocol import validate
from training.taskgen import loader
from training.taskgen.loader import SplitAccessError, load_tasks


def test_teacher_cannot_read_any_test_split():
    for split in config.TEST_SPLITS:
        with pytest.raises(SplitAccessError):
            load_tasks(split, "teacher")


def test_test_eval_cannot_read_train_or_dev():
    for split in ("train", "dev", "toy"):
        with pytest.raises(SplitAccessError):
            load_tasks(split, "test-eval")


def test_tune_reads_dev_only():
    assert load_tasks("dev", "tune", version="spike-v1")
    for split in ("train", *config.TEST_SPLITS):
        with pytest.raises(SplitAccessError):
            load_tasks(split, "tune")


def test_unknown_purpose_refused():
    with pytest.raises(SplitAccessError):
        load_tasks("dev", "whatever", version="spike-v1")


def test_every_purpose_other_than_test_eval_excludes_test_splits():
    for purpose, splits in config.SPLIT_PURPOSES.items():
        if purpose != "test-eval":
            assert not set(splits) & set(config.TEST_SPLITS), purpose


def test_mislabelled_file_is_caught(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    d = tmp_path / "tasks" / "train"
    d.mkdir(parents=True)
    (d / "v1.jsonl").write_text(json.dumps({"id": "x", "split": "test-iid"}) + "\n")
    with pytest.raises(SplitAccessError, match="labelled"):
        loader.load_tasks("train", "teacher")


def test_schema_accepts_spike_v1_and_new_splits_and_quality():
    for t in load_tasks("dev", "dev-eval", version="spike-v1"):
        assert validate("task", t) == []
    t = load_tasks("dev", "dev-eval", version="spike-v1")[0] | {
        "split": "test-real",
        "style": "terse",
        "content_key": "ab",
    }
    assert validate("task", t) == []
    spec = {
        "family": ["F6"],
        "outputs": [
            {"id": "out1", "kind": "video", "quality": {"min_ssim": 0.9, "min_psnr_db": None}}
        ],
    }
    assert validate("spec", spec) == []
    spec["outputs"][0]["quality"] = {"min_ssim": "high"}
    assert validate("spec", spec) != []
