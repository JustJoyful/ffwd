import pytest

from eval.taxonomy import CATEGORIES, classify

GRADED = {"success": False, "flags": {"ambiguous": False, "unsupported": False}}
AMBIG = {"success": False, "flags": {"ambiguous": True, "unsupported": False}}
UNSUP = {"success": False, "flags": {"ambiguous": False, "unsupported": True}}

PARSE = {
    "assistant": "x",
    "observation": {"error": "reply is not a JSON object: Expecting ',' delimiter"},
}
PROSE = {
    "assistant": "x",
    "observation": {
        "error": "extra text after the JSON object; reply with exactly one JSON object"
    },
}
SCHEMA = {
    "assistant": "x",
    "observation": {"error": "invalid action: <root>: {'action': 'run'} is not valid"},
}
REJECTED = {
    "assistant": "x",
    "observation": {
        "run_ok": False,
        "rejected": "input must be {in:<id>}",
        "stderr_tail": "rejected: ...",
    },
}
FFERR = {
    "assistant": "x",
    "observation": {"run_ok": False, "rejected": None, "stderr_tail": "Invalid argument"},
}
CHECKFAIL = {
    "assistant": "x",
    "observation": {
        "run_ok": True,
        "checks": {"out1": {"passed": False, "failed": [{"field": "video.height"}]}},
    },
}
SPEC = {"assistant": "x", "observation": {"spec": "confirmed"}}
EARLY_FINISH = {"assistant": "x", "observation": {"error": "finish requires a passing check"}}
NO_OUTPUTS = {
    "assistant": "x",
    "observation": {"run_ok": False, "error": "this request has no executable outputs"},
}


def ep(*turns, refused=False, asked=False, runs=0):
    return {"turns": list(turns), "refused": refused, "asked": asked, "runs": runs}


@pytest.mark.parametrize(
    "row,episode,expected",
    [
        ({"success": True, "flags": GRADED["flags"]}, ep(PARSE), None),
        (GRADED, ep(PARSE, PARSE, PROSE), "unparseable"),
        (GRADED, ep(SPEC, SCHEMA), "invalid_action"),
        (
            GRADED,
            ep(PARSE, REJECTED, REJECTED, runs=2),
            "invalid_action",
        ),  # rejected runs never reached ffmpeg
        (GRADED, ep(SPEC, refused=True), "refusal"),
        (GRADED, ep(REJECTED, refused=True, runs=1), "refusal"),
        (GRADED, ep(FFERR, runs=1), "wrong_command"),
        (GRADED, ep(CHECKFAIL, CHECKFAIL, runs=2), "check_fail"),
        (GRADED, ep(CHECKFAIL, FFERR, runs=2), "wrong_command"),  # the last executed run decides
        (GRADED, ep(FFERR, CHECKFAIL, runs=2), "check_fail"),
        (GRADED, ep(CHECKFAIL, refused=True, runs=1), "check_fail"),  # gave up AFTER a failed run
        (GRADED, ep(SPEC, EARLY_FINISH, SPEC), "stalled"),
        (AMBIG, ep(NO_OUTPUTS, runs=1), "missed_clarification"),
        (UNSUP, ep(CHECKFAIL, runs=1), "false_attempt"),
        (GRADED, None, "unknown_transcript_lost"),
    ],
)
def test_classify(row, episode, expected):
    got = classify(row, episode)
    assert got == expected
    assert got is None or got in CATEGORIES
