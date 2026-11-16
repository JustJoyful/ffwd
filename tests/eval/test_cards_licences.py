import pytest

from eval.cards import DATA_SECTIONS, MODEL_SECTIONS, MissingSection, data_card, model_card
from eval.licences import audit

FULL = {s: f"text for {s}" for s in MODEL_SECTIONS} | {
    "Evaluation": "| system | rate |\n|---|---|\n| M3 | 80% [70%, 87%] |"
}


def test_model_card_requires_every_section_and_a_results_table():
    text = model_card("ffmpeg-agent-v0.1-0.6b", FULL)
    assert all(f"## {s}" in text for s in MODEL_SECTIONS)
    with pytest.raises(MissingSection, match="Limitations"):
        model_card("x", {k: v for k, v in FULL.items() if k != "Limitations"})
    with pytest.raises(MissingSection, match="results table"):
        model_card("x", FULL | {"Evaluation": "looks good"})


def test_data_card_requires_every_section():
    full = {s: "x" for s in DATA_SECTIONS}
    assert "## Splits" in data_card("tasks", full)
    with pytest.raises(MissingSection):
        data_card("tasks", full | {"Licence": " "})


def test_licence_audit_flags_anything_unrecorded():
    clips = [
        {"id": "ok", "licence": "CC0", "source": "synthetic"},
        {"id": "bad", "licence": "", "source": "me"},
        {"id": "nosrc", "licence": "CC0"},
    ]
    problems = audit(clips, assets={"model": "Apache-2.0", "dataset": ""})
    assert sorted(problems) == [
        "asset dataset: no licence recorded",
        "clip bad: no licence recorded",
        "clip nosrc: no source recorded",
    ]


def test_the_shipped_corpus_and_assets_are_all_recorded():
    assert audit() == []
