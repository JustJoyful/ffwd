from pathlib import Path

import pytest

from training.corpus.make_synthetic import make_corpus


@pytest.fixture(scope="session")
def corpus_records(tmp_path_factory) -> tuple[Path, list[dict]]:
    out = tmp_path_factory.mktemp("corpus")
    return out, make_corpus(out)


@pytest.fixture(scope="session")
def corpus(corpus_records) -> dict[str, Path]:
    out, records = corpus_records
    return {r["id"]: out / r["file"] for r in records}
