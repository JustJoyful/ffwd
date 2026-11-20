import hashlib
import json

import pytest

from training import config
from training.taskgen.loader import SplitAccessError, load_extra_train
from training.taskgen.register import register
from training.taskgen.splits import assign_split


def key(i: int, want: str = "train") -> str:
    n = 0
    while True:
        k = hashlib.sha256(f"{i}:{n}".encode()).hexdigest()
        if assign_split(k, ["F1"], config.TASKGEN_SEED) == want:
            return k
        n += 1


def task(i: int, **over) -> dict:
    k = key(i)
    return {"id": f"tr-{k[:10]}-terse", "split": "train", "style": "terse", "content_key": k,
            "families": ["F1"]} | over  # fmt: skip


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "tasks"
    for split, i in (("train", 1000), ("dev", 2000)):
        (r / split).mkdir(parents=True)
        k = key(i, "train" if split == "train" else "dev")
        (r / split / "v1.jsonl").write_text(json.dumps({"id": "x", "content_key": k}) + "\n")
    (r / "MANIFEST.json").write_text(json.dumps({"splits": {"train": {}}}))
    return r


def pool(tmp_path, tasks):
    d = tmp_path / "pool"
    d.mkdir()
    (d / "tasks.jsonl").write_text("".join(json.dumps(t) + "\n" for t in tasks))
    (d / "manifest.json").write_text(json.dumps({"generator_version": "v-test"}))
    return d


def test_register_writes_identical_file_pins_hash_and_loader_verifies(tmp_path, root, monkeypatch):
    d = pool(tmp_path, [task(1), task(2)])
    entry = register(d, "hard-v1", tasks_root=root)
    blob = (d / "tasks.jsonl").read_bytes()
    assert (root / "train" / "hard-v1.jsonl").read_bytes() == blob
    assert entry["sha256"] == hashlib.sha256(blob).hexdigest() and entry["tasks"] == 2
    manifest = json.loads((root / "MANIFEST.json").read_text())
    assert manifest["splits"] == {"train": {}} and manifest["extra_train"]["hard-v1"] == entry
    monkeypatch.setattr(config, "DATA_DIR", root.parent)  # no test-* directory exists: none is read
    assert len(load_extra_train("hard-v1")) == 2
    (root / "train" / "hard-v1.jsonl").write_text("tampered\n")
    with pytest.raises(ValueError, match="pinned hash"):
        load_extra_train("hard-v1")


def test_loader_purpose_guard_still_applies(tmp_path, root, monkeypatch):
    register(pool(tmp_path, [task(1)]), "hard-v1", tasks_root=root)
    monkeypatch.setattr(config, "DATA_DIR", root.parent)
    with pytest.raises(SplitAccessError):
        load_extra_train("hard-v1", purpose="not-a-purpose")


@pytest.mark.parametrize(
    "bad, match",
    [
        ({"split": "dev"}, "split=train"),
        ({"style": "context_first"}, "TRAIN_STYLES"),
        ({"content_key": key(5, "dev")}, "hash to the train split"),
    ],
)
def test_rejects_and_writes_nothing(tmp_path, root, bad, match):
    d = pool(tmp_path, [task(1), task(2) | bad])
    before = (root / "MANIFEST.json").read_text()
    with pytest.raises(ValueError, match=match):
        register(d, "hard-v1", tasks_root=root)
    assert not (root / "train" / "hard-v1.jsonl").exists()
    assert (root / "MANIFEST.json").read_text() == before


def test_rejects_content_already_in_train_or_dev_and_duplicates(tmp_path, root):
    in_train = json.loads((root / "train" / "v1.jsonl").read_text())["content_key"]
    with pytest.raises(ValueError, match="already in train/v1"):
        register(pool(tmp_path, [task(1, content_key=in_train)]), "a", tasks_root=root)
    (tmp_path / "pool").rename(tmp_path / "pool-a")
    with pytest.raises(ValueError, match="duplicate"):
        register(pool(tmp_path, [task(3), task(3)]), "b", tasks_root=root)


def test_never_overwrites(tmp_path, root):
    d = pool(tmp_path, [task(1)])
    register(d, "hard-v1", tasks_root=root)
    with pytest.raises(FileExistsError):
        register(d, "hard-v1", tasks_root=root)
