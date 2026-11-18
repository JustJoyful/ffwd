from eval import runtime_parity as parity


def test_every_checker_conformance_case_is_loaded_with_a_unique_index():
    cases = parity.load_cases()
    assert len(cases) == 9 + 13 + 12 + 6 + 8 and [c.i for c in cases] == list(range(len(cases)))
    assert {parity.rel_out(c).split("/")[0] for c in cases} >= {
        "out1.mp4",
        "out1",
    }  # video files and frame dirs


def test_compare_flags_exec_and_verdict_differences_only():
    case = parity.Case(0, "x", "f", ["clip"], [], {"id": "out1", "kind": "video"}, True, [])
    ok = {"ok": True, "passed": True, "failed": []}
    assert parity.compare(case, ok, dict(ok)) == []
    assert "exec differs" in parity.compare(case, ok, {"ok": False, "detail": "Unknown encoder"})[0]
    assert (
        "verdict differs"
        in parity.compare(case, ok, ok | {"passed": False, "failed": ["video.rotation"]})[0]
    )
    assert (
        "recorded expectation"
        in parity.compare(case, ok | {"passed": False}, ok | {"passed": False})[0]
    )
