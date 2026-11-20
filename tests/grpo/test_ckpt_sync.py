from pathlib import Path
from types import SimpleNamespace

import pytest

from training.grpo.ckpt_sync import DirRemote, HubRemote, SyncCallback, restore_latest
from training.grpo.verify_resume import verify

FILES = [
    "adapter_model.safetensors",
    "optimizer.pt",
    "scheduler.pt",
    "rng_state.pth",
    "trainer_state.json",
]


def make_ckpt(root: Path, step: int) -> Path:
    d = root / f"checkpoint-{step}"
    d.mkdir(parents=True)
    for f in FILES:
        (d / f).write_text(f"{f}@{step}")
    return d


def test_push_then_latest_and_restore_on_a_fresh_machine(tmp_path):
    remote = DirRemote(tmp_path / "remote")
    assert remote.latest() is None
    remote.push(make_ckpt(tmp_path / "s1", 2))
    remote.push(make_ckpt(tmp_path / "s1", 4))
    assert remote.latest() == "checkpoint-4"
    fresh = tmp_path / "fresh_session"  # a brand-new Kaggle session: empty working dir
    fresh.mkdir()
    got = restore_latest(remote, fresh)
    assert got == fresh / "checkpoint-4"
    assert sorted(p.name for p in got.iterdir()) == sorted(
        FILES
    )  # optimizer, scheduler, RNG all came back
    assert (got / "optimizer.pt").read_text() == "optimizer.pt@4"


def test_restore_prefers_local_checkpoint_when_it_is_as_new(tmp_path):
    remote = DirRemote(tmp_path / "remote")
    remote.push(make_ckpt(tmp_path / "a", 4))
    local = tmp_path / "work"
    make_ckpt(local, 6)
    assert restore_latest(remote, local) == local / "checkpoint-6"


def test_restore_returns_none_when_nothing_exists(tmp_path):
    (tmp_path / "w").mkdir()
    assert restore_latest(DirRemote(tmp_path / "r"), tmp_path / "w") is None


def test_half_uploaded_checkpoint_is_never_the_latest(tmp_path):
    remote = DirRemote(tmp_path / "remote")
    remote.push(make_ckpt(tmp_path / "s", 2))
    (tmp_path / "remote" / "checkpoint-4.tmp").mkdir()  # an upload that died midway
    (tmp_path / "remote" / "checkpoint-4.tmp" / "optimizer.pt").write_text("partial")
    assert remote.latest() == "checkpoint-2"


def test_prune_keeps_only_the_newest(tmp_path):
    remote = DirRemote(tmp_path / "remote", keep_last=2)
    for step in (2, 4, 6, 8):
        remote.push(make_ckpt(tmp_path / f"s{step}", step))
    assert sorted(p.name for p in (tmp_path / "remote").iterdir()) == [
        "checkpoint-6",
        "checkpoint-8",
    ]


def test_callback_pushes_every_save_with_the_metrics_file(tmp_path):
    out = tmp_path / "ckpt"
    make_ckpt(out, 2)
    (out / "toy_metrics.jsonl").write_text('{"step": 1}\n')
    remote = DirRemote(tmp_path / "remote")
    cb = SyncCallback(remote, extra_paths=[out / "toy_metrics.jsonl"])
    cb.on_save(SimpleNamespace(output_dir=str(out)), SimpleNamespace(global_step=2), None)
    assert remote.latest() == "checkpoint-2"
    assert (
        tmp_path / "remote" / "checkpoint-2" / "toy_metrics.jsonl"
    ).read_text() == '{"step": 1}\n'


def test_crash_after_exits_only_after_the_push(tmp_path, monkeypatch):
    out = tmp_path / "ckpt"
    exits = []
    monkeypatch.setattr("os._exit", exits.append)
    remote = DirRemote(tmp_path / "remote")
    cb = SyncCallback(remote, crash_after=4)
    for step in (2, 4):
        make_ckpt(out, step)
        cb.on_save(SimpleNamespace(output_dir=str(out)), SimpleNamespace(global_step=step), None)
    assert (
        exits == [42] and remote.latest() == "checkpoint-4"
    )  # step 2 did not exit; 4 pushed first


def test_hub_remote_uses_private_repo_and_one_commit_per_checkpoint(tmp_path):
    calls = []

    class FakeApi:
        def create_repo(self, repo_id, **k):
            calls.append(("create_repo", repo_id, k.get("private"), k.get("exist_ok")))

        def upload_folder(self, **k):
            assert k["ignore_patterns"] == [
                "README.md"
            ]  # the PEFT README breaks Hub metadata validation
            calls.append(("upload_folder", k["path_in_repo"], k["repo_id"]))

        def list_repo_files(self, repo_id, **k):
            return [
                "checkpoints/checkpoint-2/optimizer.pt",
                "checkpoints/checkpoint-4/optimizer.pt",
                "README.md",
            ]

        def snapshot_download(self, **k):
            calls.append(("download", k["allow_patterns"]))

    remote = HubRemote("me/ckpt", api=FakeApi())
    remote.push(make_ckpt(tmp_path, 6))
    assert calls[0] == ("create_repo", "me/ckpt", True, True)
    assert calls[1] == ("upload_folder", "checkpoints/checkpoint-6", "me/ckpt")
    assert remote.latest() == "checkpoint-4"


def test_verify_resume_passes_for_a_continuous_run():
    rows = [{"step": s} for s in range(1, 11)]
    lr = {s: 1e-5 * (1 - (s - 1) / 10) for s in range(1, 11)}
    r = verify(rows, lr, lr0=1e-5, max_steps=10, resumed_after=6)
    assert r["ok"], r["problems"]


@pytest.mark.parametrize(
    "steps,needle",
    [
        ([1, 2, 3, 4, 5, 6, 8, 9, 10], "gap"),
        ([1, 2, 3, 4, 5, 6, 6, 7, 8, 9, 10], "duplicate"),
        ([1, 2, 3, 4, 5, 6, 1, 2, 3, 4], "restarted"),
    ],
)
def test_verify_resume_detects_broken_resumes(steps, needle):
    rows = [{"step": s} for s in steps]
    lr = {s: 1e-5 * (1 - (s - 1) / 10) for s in set(steps)}
    r = verify(rows, lr, lr0=1e-5, max_steps=10, resumed_after=6)
    assert not r["ok"] and any(needle in p for p in r["problems"]), r["problems"]


def test_verify_resume_detects_scheduler_not_restored():
    rows = [{"step": s} for s in range(1, 11)]
    lr = {s: 1e-5 * (1 - (s - 1) / 10) for s in range(1, 7)}
    lr.update({s: 1e-5 for s in range(7, 11)})  # schedule restarted at the top after resume
    r = verify(rows, lr, lr0=1e-5, max_steps=10, resumed_after=6)
    assert not r["ok"] and any("learning rate" in p for p in r["problems"])


def test_remote_from_args_picks_the_remote(tmp_path):
    from training.grpo.ckpt_sync import remote_from_args

    assert remote_from_args(None, None) is None
    assert isinstance(remote_from_args(None, tmp_path / "r", keep_last=3), DirRemote)
    pytest.importorskip("huggingface_hub")  # train dependency group
    assert isinstance(remote_from_args("me/repo", None), HubRemote)
    with pytest.raises(ValueError):
        remote_from_args("me/repo", tmp_path / "r")  # one remote at a time


def test_restore_metrics_brings_the_history_back_without_clobbering_newer_rows(tmp_path):
    from training.grpo.ckpt_sync import restore_metrics

    work = tmp_path / "work"
    ckpt = make_ckpt(work, 6)
    (ckpt / "toy_metrics.jsonl").write_text('{"step": 5}\n{"step": 6}\n')
    assert (
        restore_metrics(ckpt, work) is True
    )  # fresh session: metrics file was lost with /kaggle/working
    assert (work / "toy_metrics.jsonl").read_text() == '{"step": 5}\n{"step": 6}\n'
    (work / "toy_metrics.jsonl").write_text('{"step": 5}\n{"step": 6}\n{"step": 7}\n')
    assert restore_metrics(ckpt, work) is False  # an existing local file is never overwritten
    assert (work / "toy_metrics.jsonl").read_text().endswith('{"step": 7}\n')
