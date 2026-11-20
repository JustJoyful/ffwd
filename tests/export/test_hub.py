import hashlib

from training.export.hub import push_model


class FakeApi:
    def __init__(self):
        self.created, self.uploaded = None, {}

    def create_repo(self, repo_id, **kw):
        self.created = (repo_id, kw)

    def upload_file(self, *, path_or_fileobj, path_in_repo, repo_id, repo_type):
        with open(path_or_fileobj, "rb") as fh:
            self.uploaded[path_in_repo] = fh.read()


def test_push_model_is_private_and_uploads_files_card_and_sums(tmp_path):
    f = tmp_path / "m.gguf"
    f.write_bytes(b"weights")
    api = FakeApi()
    sums = push_model("u/m", {"m-q8_0.gguf": f}, "# card\n", api=api)
    assert api.created[1]["private"] is True and api.created[1]["repo_type"] == "model"
    assert set(api.uploaded) == {"m-q8_0.gguf", "README.md", "SHA256SUMS"}
    digest = hashlib.sha256(b"weights").hexdigest()
    assert sums == {"m-q8_0.gguf": digest}
    assert api.uploaded["SHA256SUMS"] == f"{digest}  m-q8_0.gguf\n".encode()
    assert api.uploaded["README.md"] == b"# card\n"
