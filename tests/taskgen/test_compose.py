import json
import random

import pytest

from training.protocol import validate
from training.taskgen.clips import ClipIndex
from training.taskgen.compose import (
    COMPOSABLE,
    compose,
    sample_composition,
    valid_combo,
    valid_combos,
)
from training.taskgen.families import SAMPLERS
from training.taskgen.phrasing import BANK
from training.taskgen.special import AMBIGUOUS, UNSUPPORTED, sample_ambiguous, sample_unsupported
from training.taskgen.verify import draft_task_core, verify_task


@pytest.fixture(scope="module")
def ci(corpus_records):
    out, records = corpus_records
    (out / "manifest.json").write_text(json.dumps(records))
    return ClipIndex(out / "manifest.json")


def test_incompatible_families_never_combine():
    assert (
        not valid_combo(("F7", "F6"))
        and not valid_combo(("F11", "F1"))
        and not valid_combo(("F2", "F10"))
    )
    assert valid_combo(("F1", "F4", "F5", "F12"))
    assert all(len(valid_combos(k)) > 0 for k in (2, 3, 4))
    assert all(a not in COMPOSABLE[a] for a in COMPOSABLE)


def test_two_trims_conflict_and_contradictory_audio_ops_are_refused(ci):
    a = SAMPLERS["F1"](random.Random(1), ci)
    b = SAMPLERS["F1"](random.Random(2), ci, clip=a.inputs[0])
    assert compose([a, b], ci) is None  # two trims
    rm = SAMPLERS["F9"](random.Random(0), ci)
    while "f9.remove" not in rm.intents:
        rm = SAMPLERS["F9"](random.Random(random.random()), ci)
    loud = SAMPLERS["F10"](random.Random(3), ci, clip=rm.inputs[0])
    assert (
        loud is None or compose([rm, loud], ci) is None
    )  # "remove the sound" vs "set its loudness"


@pytest.mark.parametrize("k", [2, 3, 4])
def test_composed_reference_passes_the_checker(k, ci, corpus_records, tmp_path):
    corpus = {c.id: c.path for c in ci.clips.values()}
    made = 0
    for seed in range(40):
        d = sample_composition(random.Random(f"t{k}-{seed}"), ci, k)
        if d is None:
            continue
        task = draft_task_core(d, ci) | {"id": f"c{k}-{seed}"}
        row = verify_task(task, corpus, tmp_path / str(seed))
        assert row["passed"], (d.families, task["reference_runs"][0]["args"], row["failed"])
        assert d.difficulty == k and len(set(d.families)) == k
        made += 1
        if made == 3:
            break
    assert made == 3


def test_ambiguous_and_unsupported_samples_are_well_formed(ci):
    for i in range(20):
        amb = sample_ambiguous(random.Random(i), ci)
        assert amb["intent"] in AMBIGUOUS and amb["intent"] in BANK and amb["clarification"]
        assert amb["ambiguous"] and not amb["unsupported"] and len(amb["families"]) == 1
        uns = sample_unsupported(random.Random(i), ci)
        assert (
            uns["intent"] in UNSUPPORTED
            and uns["families"] == []
            and uns["nearest_supported"] in (None, "F4")
        )


def test_every_special_intent_has_wordings():
    for intent in (*AMBIGUOUS, *UNSUPPORTED):
        assert len(BANK[intent]["core"]) >= 3 and BANK[intent]["symptom"]


def test_unsupported_task_schema_allows_empty_families():
    task = {
        "id": "u-x", "split": "train", "source": "taskgen-1.0", "request": "remove the person", "inputs": ["clip_a"],
        "gold_spec": None, "families": [], "nearest_supported": None, "difficulty": 1,
        "flags": {"ambiguous": False, "unsupported": True}, "clarification": None, "reference_runs": None,
    }  # fmt: skip
    assert validate("task", task) == []
