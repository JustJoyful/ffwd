import json

import pytest

from eval.testlock import NotPreregistered, TestAlreadyRun, acquire_test_run

FINAL = "Phase 1 status: FINAL\n"


@pytest.fixture
def prereg(tmp_path):
    p = tmp_path / "PREREG.md"
    p.write_text(FINAL)
    return p


def _acquire(tmp_path, prereg, system="M3", ckpt="step-90", split="test-iid", **kw):
    acquire_test_run(system, ckpt, split, ledger=tmp_path / "runs.jsonl", prereg=prereg, **kw)


def test_second_test_run_is_refused(tmp_path, prereg):
    _acquire(tmp_path, prereg)
    with pytest.raises(TestAlreadyRun):
        _acquire(tmp_path, prereg)


def test_other_system_checkpoint_or_split_is_independent(tmp_path, prereg):
    _acquire(tmp_path, prereg)
    _acquire(tmp_path, prereg, system="M1")
    _acquire(tmp_path, prereg, ckpt="step-60")
    _acquire(tmp_path, prereg, split="test-phrasing")


def test_supersede_needs_a_reason_and_is_logged(tmp_path, prereg):
    _acquire(tmp_path, prereg)
    with pytest.raises(TestAlreadyRun):
        _acquire(tmp_path, prereg, supersede_reason="  ")
    _acquire(tmp_path, prereg, supersede_reason="server crashed mid-run, no results were read")
    last = json.loads((tmp_path / "runs.jsonl").read_text().splitlines()[-1])
    assert last["superseded"] and "crashed" in last["supersede_reason"]


def test_refused_unless_preregistration_is_final(tmp_path):
    draft = tmp_path / "P.md"
    draft.write_text("Phase 1 status: DRAFT\n")
    with pytest.raises(NotPreregistered):
        _acquire(tmp_path, draft)
    with pytest.raises(NotPreregistered):
        _acquire(tmp_path, tmp_path / "missing.md")


def test_dev_and_train_splits_are_unaffected_and_never_logged(tmp_path):
    for split in ("dev", "train", "toy"):
        acquire_test_run(
            "M1", "x", split, ledger=tmp_path / "runs.jsonl", prereg=tmp_path / "nope.md"
        )
    assert not (tmp_path / "runs.jsonl").exists()


def test_oracle_ablation_is_never_run_on_a_test_split(tmp_path):
    import pytest

    from eval.testlock import acquire_test_run

    with pytest.raises(PermissionError, match="dev-only"):
        acquire_test_run("M1-oracle", "ckpt", "test-iid", ledger=tmp_path / "l.jsonl")
