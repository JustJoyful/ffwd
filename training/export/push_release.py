"""Upload a built release package to a PRIVATE Hugging Face model repo and tag it. Two separate steps, both DRY RUN
by default; a real action needs `--go`. Visibility is never touched here (making a repo public is a manual owner action).

    uv run python -m training.export.push_release rename --from JustJoyful/<existing-private-repo> [--go]
    uv run python -m training.export.push_release upload --package releases/ffwd-0.6b-v1.0.0 [--delete-stale] [--go]

`upload` makes ONE commit with every file of the package and then tags that exact commit (`create_tag(revision=oid)`),
so the tag, and the revision the website pins, is the uploaded content. `--move-tag` (with `--go`, private repos only)
re-points an existing tag at the new commit; without it an existing tag is refused. Needs `hf auth login` with write access.
"""

import argparse
import json
import sys
from pathlib import Path

from training.export.release import verify_package

REPO_ID = "JustJoyful/ffwd-0.6b"
IGNORE_REMOTE = {".gitattributes"}


class PushError(Exception):
    pass


def _repo_private(api, repo_id: str) -> bool | None:
    """True/False for an existing repo, None when it does not exist (a read, never a write)."""
    from huggingface_hub.errors import RepositoryNotFoundError

    try:
        return bool(api.repo_info(repo_id, repo_type="model").private)
    except RepositoryNotFoundError:
        return None


def rename(src: str, dst: str, *, go: bool, api=None, say=print) -> None:
    if api is None:
        from huggingface_hub import HfApi

        api = HfApi()
    if _repo_private(api, src) is not True:
        raise PushError(f"{src} does not exist or is not private: refusing")
    if _repo_private(api, dst) is not None:
        raise PushError(f"{dst} already exists: refusing")
    say(
        f"{'RENAME' if go else 'DRY RUN: would rename'} {src} -> {dst} (model repo; the old name redirects; "
        "the whole git history, files included, moves with it; visibility unchanged)"
    )
    if go:
        api.move_repo(from_id=src, to_id=dst, repo_type="model")


def upload(
    package: Path,
    repo_id: str,
    tag: str | None,
    *,
    go: bool,
    delete_stale: bool = False,
    move_tag: bool = False,
    api=None,
    say=print,
) -> str | None:
    """Returns the commit oid with --go, else None."""
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete

    problems = verify_package(package)
    if problems:
        raise PushError("package does not verify, refusing: " + "; ".join(problems))
    version = json.loads((package / "ffwd-model.json").read_text())["version"]
    tag = tag or f"v{version}"
    if tag != f"v{version}":
        raise PushError(f"tag {tag} does not match the package version v{version}")
    if api is None:
        from huggingface_hub import HfApi

        api = HfApi()
    files = sorted(p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file())
    private = _repo_private(api, repo_id)
    if private is False:
        raise PushError(f"{repo_id} is PUBLIC: this script only uploads to private repos")
    stale: list[str] = []
    moving = False
    if private is None:
        say(f"{repo_id} does not exist: would create it (private=True)")
    else:
        tags = {
            t.name.removeprefix("refs/tags/")
            for t in api.list_repo_refs(repo_id, repo_type="model").tags
        }
        if tag in tags and not move_tag:
            raise PushError(f"tag {tag} already exists on {repo_id} (--move-tag moves it)")
        moving = tag in tags
        stale = sorted(
            set(api.list_repo_files(repo_id, repo_type="model")) - set(files) - IGNORE_REMOTE
        )
        if stale:
            say(f"files on {repo_id} that are not in the package: {stale}")
            if go and not delete_stale:
                raise PushError("remote has files outside the package: re-run with --delete-stale")
    say(
        f"{'UPLOAD' if go else 'DRY RUN: would upload'} {len(files)} files to {repo_id} in one commit: {files}"
    )
    if stale and delete_stale:
        say(f"{'deleting' if go else 'would delete'} in the same commit: {stale}")
    if moving:
        say(f"{'then' if go else 'would then'} DELETE tag {tag} and re-create it on the new commit")
    say(
        f"then {'create' if go else 'would create'} tag {tag} on that commit (private repo, visibility untouched)"
    )
    if not go:
        return None
    api.create_repo(repo_id, repo_type="model", private=True, exist_ok=True)
    ops = [CommitOperationAdd(path_in_repo=f, path_or_fileobj=str(package / f)) for f in files]
    ops += [CommitOperationDelete(path_in_repo=f) for f in stale if delete_stale]
    info = api.create_commit(
        repo_id, ops, repo_type="model", commit_message=f"ffwd-0.6b v{version}"
    )
    if moving:
        if _repo_private(api, repo_id) is not True:  # re-check right before the destructive step
            raise PushError(f"{repo_id} is not private any more: tag {tag} NOT moved")
        api.delete_tag(repo_id, tag=tag, repo_type="model")
    api.create_tag(repo_id, tag=tag, revision=info.oid, repo_type="model")
    say(f"committed {info.oid} and tagged {tag}; private={_repo_private(api, repo_id)}")
    return info.oid


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="push_release", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rename", help="move_repo of an existing private repo to the release id")
    r.add_argument(
        "--from", dest="src", required=True, help="no default: you choose which repo moves"
    )
    r.add_argument("--to", default=REPO_ID)
    u = sub.add_parser(
        "upload", help="one commit with the package, then the version tag on that commit"
    )
    u.add_argument("--package", type=Path, required=True)
    u.add_argument("--repo", default=REPO_ID)
    u.add_argument("--tag", default=None)
    u.add_argument(
        "--delete-stale",
        action="store_true",
        help="delete remote files that are not in the package",
    )
    u.add_argument(
        "--move-tag",
        action="store_true",
        help="the tag already exists: delete it and re-create it on the new commit (private repos only; "
        "real only with --go, otherwise the dry run prints it)",
    )
    for p in (r, u):
        p.add_argument("--go", action="store_true", help="really do it (default: dry run)")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "rename":
            rename(a.src, a.to, go=a.go)
        else:
            upload(
                a.package, a.repo, a.tag, go=a.go, delete_stale=a.delete_stale, move_tag=a.move_tag
            )
    except PushError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
