import json
import tarfile

from training.sft.kaggle_sft import SCRIPT, package


def test_package_holds_the_commit_code_and_data_and_no_secrets(tmp_path):
    data = tmp_path / "d"
    data.mkdir()
    for n in ("examples.jsonl", "val.jsonl", "stats.json"):
        (data / n).write_text("{}\n")
    out = package(data, tmp_path / "pkg", "HEAD")
    with tarfile.open(out / "code.tar") as t:
        names = t.getnames()
        commit = t.extractfile("COMMIT").read().decode().strip()
    assert len(commit) == 40 and "training/sft/train.py" in names and "pyproject.toml" in names
    assert not any(
        n.startswith(("data/", "reports/", "eval/")) for n in names
    )  # no data, reports or held-out code
    assert json.loads((out / "dataset-metadata.json").read_text())["id"].endswith(
        "/ffmpeg-agent-sft-v1"
    )
    assert all((out / n).exists() for n in ("examples.jsonl", "val.jsonl", "stats.json"))
    assert "get_secret" not in SCRIPT and "token" not in SCRIPT.lower()


def test_kernel_script_is_valid_python_and_handles_both_dataset_layouts():
    src = SCRIPT.format(epochs=2, save_steps=50)
    compile(src, "run.py", "exec")  # a syntax slip would only show up after the Kaggle queue
    assert "examples.jsonl" in src and "/code" in src and "code.tar" in src
