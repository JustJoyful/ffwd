"""Push every GRPO checkpoint off the training box and restore from it in a fresh session (T5, D-022).

Why: Kaggle wipes /kaggle/working when a session dies (idle timeout, crash, 12 h limit). The Phase 0
Kaggle run lost its checkpoints exactly that way. A checkpoint-N directory written by the HF Trainer
holds everything needed to resume: adapter weights, optimizer.pt, scheduler.pt, rng_state.pth and
trainer_state.json (global step; the Trainer skips already-consumed batches on resume).

Torch-free on purpose: the remote is pluggable (a directory for tests and local runs, the HF Hub for
real runs), and only the TrainerCallback hook needs transformers' duck-typed args/state objects.
"""

import re
import shutil
from pathlib import Path
from typing import Protocol

_CKPT = re.compile(r"^checkpoint-(\d+)$")


def _step(name: str) -> int:
    m = _CKPT.match(name)
    return int(m.group(1)) if m else -1


class Remote(Protocol):
    def push(self, ckpt_dir: Path, extra_files: list[Path] | None = None) -> None: ...
    def latest(self) -> str | None: ...
    def pull(self, name: str, dest_root: Path) -> Path: ...


class DirRemote:
    """A directory acting as the remote (tests, local runs). Uploads land in `<name>.tmp` and are
    renamed only when complete, so a half-copied checkpoint can never be picked as the latest."""

    def __init__(self, root: Path, keep_last: int | None = None):
        self.root, self.keep_last = Path(root), keep_last
        self.root.mkdir(parents=True, exist_ok=True)

    def push(self, ckpt_dir: Path, extra_files: list[Path] | None = None) -> None:
        tmp, final = self.root / f"{ckpt_dir.name}.tmp", self.root / ckpt_dir.name
        if tmp.exists():
            shutil.rmtree(tmp)
        shutil.copytree(ckpt_dir, tmp)
        for f in extra_files or []:
            if f.exists():
                shutil.copy2(f, tmp / f.name)
        if final.exists():
            shutil.rmtree(final)
        tmp.rename(final)
        if self.keep_last:
            done = sorted(
                (p for p in self.root.iterdir() if _step(p.name) >= 0), key=lambda p: _step(p.name)
            )
            for old in done[: -self.keep_last]:
                shutil.rmtree(old)

    def latest(self) -> str | None:
        done = [p.name for p in self.root.iterdir() if _step(p.name) >= 0]
        return max(done, key=_step) if done else None

    def pull(self, name: str, dest_root: Path) -> Path:
        dest = dest_root / name
        shutil.copytree(self.root / name, dest)
        return dest


class HubRemote:
    """A private Hugging Face Hub repo: one commit per checkpoint under checkpoints/checkpoint-N/.

    upload_folder is a single atomic commit, so a checkpoint is visible only when fully uploaded.
    Needs a token with write access (Kaggle: the HF_TOKEN secret).
    """

    PREFIX = "checkpoints"

    def __init__(self, repo_id: str, api=None, token: str | None = None):
        if api is None:
            from huggingface_hub import HfApi

            api = HfApi(token=token)
        self.repo_id, self.api, self.token = repo_id, api, token
        self._created = False

    def _ensure_repo(self) -> None:
        if not self._created:
            self.api.create_repo(self.repo_id, private=True, exist_ok=True)
            self._created = True

    def push(self, ckpt_dir: Path, extra_files: list[Path] | None = None) -> None:
        self._ensure_repo()
        for f in extra_files or []:
            if f.exists() and f.parent != ckpt_dir:
                shutil.copy2(
                    f, ckpt_dir / f.name
                )  # the metrics file travels inside the checkpoint commit
        self.api.upload_folder(
            folder_path=str(ckpt_dir),
            repo_id=self.repo_id,
            path_in_repo=f"{self.PREFIX}/{ckpt_dir.name}",
            commit_message=f"{ckpt_dir.name}",
        )

    def latest(self) -> str | None:
        try:
            files = self.api.list_repo_files(self.repo_id)
        except Exception:  # repo missing: nothing to resume from
            return None
        steps = {
            p.split("/")[1] for p in files if p.startswith(f"{self.PREFIX}/") and p.count("/") >= 2
        }
        return max(steps, key=_step) if steps else None

    def pull(self, name: str, dest_root: Path) -> Path:
        tmp = dest_root / ".hub_tmp"
        self.api.snapshot_download(
            repo_id=self.repo_id,
            allow_patterns=[f"{self.PREFIX}/{name}/*"],
            local_dir=str(tmp),
        )
        dest = dest_root / name
        shutil.move(str(tmp / self.PREFIX / name), str(dest))
        shutil.rmtree(tmp, ignore_errors=True)
        return dest


def local_latest(ckpt_dir: Path) -> Path | None:
    found = [p for p in ckpt_dir.glob("checkpoint-*") if p.is_dir() and _step(p.name) >= 0]
    return max(found, key=lambda p: _step(p.name)) if found else None


def restore_latest(remote: Remote, ckpt_dir: Path) -> Path | None:
    """The checkpoint to resume from: the newest of (local, remote); downloads the remote one if newer."""
    local = local_latest(ckpt_dir)
    name = remote.latest()
    if name is None or (local is not None and _step(local.name) >= _step(name)):
        return local
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    return remote.pull(name, ckpt_dir)


def remote_from_args(
    hub_repo: str | None, sync_dir: Path | None, keep_last: int | None = None
) -> Remote | None:
    """The remote chosen by CLI flags: a private HF Hub repo (real runs), a directory (local), or none."""
    if hub_repo and sync_dir:
        raise ValueError("choose one remote: --hub-repo or --sync-dir")
    if hub_repo:
        import os

        return HubRemote(hub_repo, token=os.environ.get("HF_TOKEN"))
    return DirRemote(Path(sync_dir), keep_last=keep_last) if sync_dir else None


def restore_metrics(ckpt: Path, ckpt_dir: Path, name: str = "toy_metrics.jsonl") -> bool:
    """Copy the metrics history that travelled inside the checkpoint back to the working dir.

    The checkpoint's copy ends at the saved step, so resuming appends from there with no duplicate rows.
    Never overwrites an existing local file (same session resumed in place).
    """
    src, dst = ckpt / name, ckpt_dir / name
    if src.exists() and not dst.exists():
        shutil.copy2(src, dst)
        return True
    return False


class SyncCallback:
    """transformers.TrainerCallback duck type: push checkpoint-N (plus metrics/telemetry/pass-rate files) on every save."""

    def __init__(self, remote: Remote, extra_paths: list[Path] | None = None):
        self.remote, self.extra_paths = remote, extra_paths or []

    def on_save(self, args, state, control, **kw):
        ckpt = Path(args.output_dir) / f"checkpoint-{state.global_step}"
        self.remote.push(ckpt, self.extra_paths)

    def __getattr__(self, name):  # every other TrainerCallback hook is a no-op
        if name.startswith("on_"):
            return lambda *a, **k: None
        raise AttributeError(name)
