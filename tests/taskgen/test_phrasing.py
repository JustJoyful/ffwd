import ast
import random
import re
from pathlib import Path

import pytest

from training import config
from training.taskgen.clips import ClipIndex
from training.taskgen.families import SAMPLERS
from training.taskgen.phrasing import BANK, TRAIN_STYLES, render_request
from training.taskgen.phrasing_heldout import HELDOUT_STYLES, TECH

NUM = re.compile(r"\d+(?::\d+)*(?:\.\d+)?")


@pytest.fixture(scope="module")
def drafts(corpus_records):
    import json

    out, records = corpus_records
    (out / "manifest.json").write_text(json.dumps(records))
    ci = ClipIndex(out / "manifest.json")
    found = {}
    for fid, fn in SAMPLERS.items():
        for seed in range(80):
            d = fn(random.Random(f"{fid}-{seed}"), ci)
            if d is not None:
                found.setdefault(d.intents[0], d)
    return found


def test_every_intent_has_enough_wordings():
    for intent, forms in BANK.items():
        assert (
            len(forms["core"]) >= 3 and len(forms["cont"]) >= 1 and len(forms["symptom"]) >= 1
        ), intent


def test_every_sampled_intent_is_in_the_bank_and_every_bank_intent_is_reachable(drafts):
    from training.taskgen.special import AMBIGUOUS, UNSUPPORTED

    assert set(drafts) <= set(BANK)
    special = set(AMBIGUOUS) | set(UNSUPPORTED)
    assert set(BANK) - set(drafts) - special == set()


@pytest.mark.parametrize("style", [*TRAIN_STYLES, *HELDOUT_STYLES])
def test_all_styles_render_every_intent_with_only_slot_digits(drafts, style):
    rng = random.Random(3)
    for intent, d in drafts.items():
        text = render_request(d.intents, d.slots, style, rng)
        allowed = set(NUM.findall(" ".join(d.slots.values())))
        allowed |= set(
            NUM.findall(" ".join(sum(BANK[intent].values(), []) + sum(TECH.values(), [])))
        )
        assert set(NUM.findall(text)) <= allowed, (intent, style, text)


def test_train_styles_are_distinct_from_each_other(drafts):
    d = drafts["f1.keep_range"]
    texts = {render_request(d.intents, d.slots, s, random.Random(5)) for s in TRAIN_STYLES}
    assert len(texts) >= 4


def test_heldout_styles_differ_from_every_train_wording(drafts):
    d = drafts["f4.height"]
    train = {
        render_request(d.intents, d.slots, s, random.Random(i))
        for s in TRAIN_STYLES
        for i in range(20)
    }
    for s in HELDOUT_STYLES:
        assert render_request(d.intents, d.slots, s, random.Random(0)) not in train


def test_typo_noise_never_touches_digits():
    from training.taskgen.phrasing import typo

    for i in range(50):
        out = typo(
            "make this video 1080 by 1920 and keep the aspect ratio", random.Random(i), p=1.0
        )
        assert NUM.findall(out) == ["1080", "1920"]


def test_heldout_module_is_imported_only_by_phrasing_and_build():
    allowed = {
        "training/taskgen/phrasing.py",
        "training/taskgen/build.py",
        "tests/taskgen/test_phrasing.py",
    }
    offenders = []
    for path in list(Path(config.REPO_ROOT, "training").rglob("*.py")) + list(
        Path(config.REPO_ROOT, "eval").rglob("*.py")
    ):
        rel = path.relative_to(config.REPO_ROOT).as_posix()
        if rel == "training/taskgen/phrasing_heldout.py" or rel in allowed:
            continue
        if "phrasing_heldout" in path.read_text():
            offenders.append(rel)
    assert offenders == []
    ast.parse(Path(config.REPO_ROOT, "training/taskgen/phrasing.py").read_text())


def test_heldout_styles_cover_every_intent_including_ambiguous_and_unsupported():
    for intent in BANK:
        slots = {k: "1" for k in "nsedwhmbivfpl"} | {
            "s_mmss": "0:01",
            "e_mmss": "0:02",
            "fmt": "PNG",
            "res": "720p",
            "count": "two",
            "sec": "1",
            "ms": "100",
            "db": "6",
            "lufs": "-16",
            "fps": "30",
            "mb": "2",
            "iv": "2",
        }
        for style in HELDOUT_STYLES:
            assert render_request([intent], slots, style, random.Random(0)), (intent, style)
