"""Push a trained model to a PRIVATE HF model repo with a model card and a SHA256SUMS file.

The card must come from `eval.cards.model_card` (every required section present); this module only uploads.
Tests inject a fake `api`; real use needs an HF token with write access (`hf auth login`).
"""

import hashlib
import tempfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def push_model(repo_id: str, files: dict[str, Path], card: str, api=None) -> dict[str, str]:
    """Create the private repo if needed and upload `files` ({path in repo: local file}), README.md and SHA256SUMS.
    Returns {path in repo: sha256}."""
    if api is None:
        from huggingface_hub import HfApi

        api = HfApi()
    sums = {name: sha256_file(p) for name, p in files.items()}
    api.create_repo(repo_id, repo_type="model", private=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        readme, sumfile = Path(d) / "README.md", Path(d) / "SHA256SUMS"
        readme.write_text(card)
        sumfile.write_text("".join(f"{h}  {n}\n" for n, h in sorted(sums.items())))
        uploads = {**files, "README.md": readme, "SHA256SUMS": sumfile}
        for name, path in uploads.items():
            api.upload_file(
                path_or_fileobj=str(path), path_in_repo=name, repo_id=repo_id, repo_type="model"
            )
    return sums
