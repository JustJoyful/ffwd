"""push_release with a recording fake HfApi: a dry run writes nothing, --go acts in order, private is enforced."""

from types import SimpleNamespace

import pytest
from huggingface_hub.errors import RepositoryNotFoundError

from training.export.push_release import PushError, rename, upload
from training.export.release import build

WRITES = (
    "create_repo",
    "create_commit",
    "create_tag",
    "delete_tag",
    "move_repo",
    "update_repo_settings",
)


class FakeApi:
    def __init__(self, repos=None, files=(), tags=()):
        self.repos = dict(repos or {})  # repo id -> private
        self.files, self.tags, self.calls = list(files), list(tags), []

    def repo_info(self, repo_id, **kw):
        if repo_id not in self.repos:
            raise RepositoryNotFoundError(
                "nope", response=SimpleNamespace(headers={}, request=None, status_code=404)
            )
        return SimpleNamespace(private=self.repos[repo_id])

    def list_repo_files(self, repo_id, **kw):
        return self.files

    def list_repo_refs(self, repo_id, **kw):
        return SimpleNamespace(tags=[SimpleNamespace(name=f"refs/tags/{t}") for t in self.tags])

    def create_repo(self, repo_id, **kw):
        self.calls.append(("create_repo", repo_id, kw))
        self.repos.setdefault(repo_id, kw["private"])

    def create_commit(self, repo_id, operations, **kw):
        self.calls.append(
            (
                "create_commit",
                repo_id,
                sorted((type(o).__name__, o.path_in_repo) for o in operations),
            )
        )
        return SimpleNamespace(oid="c0ffee")

    def create_tag(self, repo_id, **kw):
        self.calls.append(("create_tag", repo_id, kw))

    def delete_tag(self, repo_id, **kw):
        self.calls.append(("delete_tag", repo_id, kw))
        self.tags.remove(kw["tag"])

    def move_repo(self, **kw):
        self.calls.append(("move_repo", kw))
        self.repos[kw["to_id"]] = self.repos.pop(kw["from_id"])

    def names(self):
        return [c[0] for c in self.calls]


@pytest.fixture
def package(inputs, tmp_path):
    build(inputs, "1.0.0", tmp_path / "pkg")
    return tmp_path / "pkg"


def test_dry_run_does_nothing_for_new_and_existing_repos(package):
    for repos in ({}, {"u/r": True}):
        api, out = FakeApi(repos), []
        assert upload(package, "u/r", None, go=False, api=api, say=out.append) is None
        assert api.calls == [] and any("DRY RUN" in line for line in out)


def test_go_creates_private_repo_commits_all_files_then_tags_that_commit(package):
    api = FakeApi()
    assert upload(package, "u/r", None, go=True, api=api, say=lambda _m: None) == "c0ffee"
    assert api.names() == ["create_repo", "create_commit", "create_tag"]
    assert api.calls[0][2]["private"] is True and api.repos["u/r"] is True
    adds = [p for kind, p in api.calls[1][2] if kind == "CommitOperationAdd"]
    assert (
        "ffwd-model.json" in adds
        and "SHA256SUMS" in adds
        and "adapter/adapter_model.safetensors" in adds
    )
    assert api.calls[2][2]["tag"] == "v1.0.0" and api.calls[2][2]["revision"] == "c0ffee"
    assert not any(n == "update_repo_settings" for n in api.names())


def test_public_repo_is_refused(package):
    api = FakeApi({"u/r": False})
    with pytest.raises(PushError, match="PUBLIC"):
        upload(package, "u/r", None, go=True, api=api, say=lambda _m: None)
    assert api.calls == []


def test_existing_tag_and_wrong_tag_are_refused(package):
    with pytest.raises(PushError, match="already exists"):
        upload(
            package,
            "u/r",
            None,
            go=True,
            api=FakeApi({"u/r": True}, tags=["v1.0.0"]),
            say=lambda _m: None,
        )
    with pytest.raises(PushError, match="does not match"):
        upload(package, "u/r", "v2.0.0", go=False, api=FakeApi(), say=lambda _m: None)


def test_move_tag_dry_run_prints_and_writes_nothing(package):
    api, out = FakeApi({"u/r": True}, tags=["v1.0.0"]), []
    assert upload(package, "u/r", None, go=False, move_tag=True, api=api, say=out.append) is None
    assert api.calls == [] and any("DELETE tag v1.0.0" in line for line in out)


def test_move_tag_go_commits_then_deletes_and_recreates_the_tag(package):
    api = FakeApi({"u/r": True}, tags=["v1.0.0"])
    upload(package, "u/r", None, go=True, move_tag=True, api=api, say=lambda _m: None)
    assert api.names() == ["create_repo", "create_commit", "delete_tag", "create_tag"]
    assert (
        api.calls[-1][2]["revision"] == "c0ffee" and api.tags == []
    )  # fake tags list is not re-added
    assert not any(n == "update_repo_settings" for n in api.names())


def test_move_tag_refuses_public_repo_and_never_deletes_without_the_flag(package):
    pub = FakeApi({"u/r": False}, tags=["v1.0.0"])
    with pytest.raises(PushError, match="PUBLIC"):
        upload(package, "u/r", None, go=True, move_tag=True, api=pub, say=lambda _m: None)
    assert pub.calls == []
    api = FakeApi({"u/r": True}, tags=["v1.0.0"])
    with pytest.raises(PushError, match="already exists"):
        upload(package, "u/r", None, go=True, api=api, say=lambda _m: None)
    assert api.calls == []


def test_move_tag_rechecks_privacy_before_deleting(package):
    class Flip(FakeApi):
        def create_commit(self, *a, **kw):
            self.repos["u/r"] = False  # made public behind our back
            return super().create_commit(*a, **kw)

    api = Flip({"u/r": True}, tags=["v1.0.0"])
    with pytest.raises(PushError, match="not private any more"):
        upload(package, "u/r", None, go=True, move_tag=True, api=api, say=lambda _m: None)
    assert "delete_tag" not in api.names()


def test_stale_remote_files_need_delete_stale(package):
    api = FakeApi({"u/r": True}, files=[".gitattributes", "old-m1.gguf", "README.md"])
    with pytest.raises(PushError, match="delete-stale"):
        upload(package, "u/r", None, go=True, api=api, say=lambda _m: None)
    assert api.calls == []
    upload(package, "u/r", None, go=True, delete_stale=True, api=api, say=lambda _m: None)
    assert ("CommitOperationDelete", "old-m1.gguf") in api.calls[1][2]


def test_package_that_fails_sha256sums_is_refused(package):
    (package / "README.md").write_text("tampered")
    api = FakeApi()
    with pytest.raises(PushError, match="does not verify"):
        upload(package, "u/r", None, go=True, api=api, say=lambda _m: None)
    assert api.calls == []


def test_rename_dry_run_then_go(package):
    api = FakeApi({"u/old": True})
    rename("u/old", "u/new", go=False, api=api, say=lambda _m: None)
    assert api.calls == []
    rename("u/old", "u/new", go=True, api=api, say=lambda _m: None)
    assert api.names() == ["move_repo"] and api.calls[0][1] == {
        "from_id": "u/old",
        "to_id": "u/new",
        "repo_type": "model",
    }


def test_rename_refuses_public_source_missing_source_and_existing_target():
    for repos in ({"u/old": False}, {}, {"u/old": True, "u/new": True}):
        api = FakeApi(repos)
        with pytest.raises(PushError):
            rename("u/old", "u/new", go=True, api=api, say=lambda _m: None)
        assert api.calls == []
