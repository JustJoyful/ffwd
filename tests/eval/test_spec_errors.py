from eval.spec_errors import applicable, material_errors, summarize


def spec(**out):
    return {"family": ["F1"], "outputs": [{"id": "out1", "kind": "video"} | out]}


GOLD = spec(
    container="mp4",
    video={"width": 1280, "height": 720},
    time={"start_s": 5, "end_s": 10, "tolerance_s": 0.2},
)


def test_equal_or_over_specified_spec_has_no_material_error():
    assert material_errors(GOLD, GOLD) == []
    over = spec(
        container="mp4",
        video={"width": 1280, "height": 720, "codec": "h264", "fps": 30, "pix_fmt": "yuv420p"},
        time={"start_s": 5, "end_s": 10, "tolerance_s": 0.5},
        audio={"present": True, "codec": "aac"},
    )
    assert (
        material_errors(over, GOLD) == []
    )  # extras, tolerances, an unconstrained audio codec: style
    near = spec(
        container="mp4",
        video={"width": 1281, "height": 719},
        time={"start_s": 5.1, "end_s": 10.15},
    )
    assert material_errors(near, GOLD) == []  # within 2 px and the gold tolerance


def test_wrong_missing_and_swapped_values_are_material_errors():
    wrong = spec(
        container="matroska",
        video={"width": 1280, "height": 720},
        time={"start_s": 5, "end_s": 10},
    )
    assert material_errors(wrong, GOLD) == ["container"]
    swapped = spec(
        container="mp4", video={"width": 720, "height": 1280}, time={"start_s": 5, "end_s": 10}
    )
    assert sorted(material_errors(swapped, GOLD)) == ["video.height", "video.width"]
    late = spec(container="mp4", video={"width": 1280, "height": 720}, time={"end_s": 12})
    assert material_errors(late, GOLD) == ["time.start_s", "time.end_s"]
    assert "video.width" in material_errors(spec(container="mp4"), GOLD)  # omitting counts


def test_an_omitted_container_is_not_an_error_but_a_wrong_one_is():
    gold = spec(container="mp4", video={"width": 640})
    assert (
        material_errors(spec(video={"width": 640}), gold) == []
    )  # the gold's container is a default
    assert material_errors(spec(container="matroska", video={"width": 640}), gold) == ["container"]


def test_codec_counts_only_when_the_gold_spec_constrains_it():
    gold = spec(video={"codec": "h265"})
    assert material_errors(spec(video={"codec": "h264"}), gold) == ["video.codec"]
    assert material_errors(spec(video={"codec": "h264"}), spec(video={"fps": 30})) == []


def test_lossless_omission_and_false_claim():
    gold = spec(lossless=True)
    assert material_errors(spec(container="mp4"), gold) == ["lossless"]
    assert material_errors(spec(lossless=True), gold, re_encoded=False) == []
    claim = material_errors(spec(lossless=True), spec(video={"fps": 30}), re_encoded=True)
    assert claim == ["lossless_claim_false"]
    assert material_errors(spec(lossless=True), gold, re_encoded=True) == ["lossless_claim_false"]


def task(i, gold, ambiguous=False, unsupported=False):
    return {
        "id": i,
        "flags": {"ambiguous": ambiguous, "unsupported": unsupported},
        "gold_spec": gold,
    }


def test_a_system_with_no_spec_step_is_not_applicable_but_a_spec_first_model_that_skips_one_is_wrong():
    from eval.spec_errors import fmt

    tasks = {"a": task("a", GOLD), "b": task("b", GOLD)}
    none = summarize(tasks, {"a": {"emitted_spec": None}, "b": {"emitted_spec": None}})
    assert not none["emits_spec"] and fmt(none) == "n/a (emits no spec)"
    some = summarize(tasks, {"a": {"emitted_spec": GOLD}, "b": {"emitted_spec": None}})
    assert some["emits_spec"] and some["errors"] == 1 and fmt(some).startswith("1/2")


def test_applicable_and_the_rate_keeps_no_spec_episodes_in_the_denominator():
    tasks = {
        t["id"]: t
        for t in [
            task("a", GOLD),
            task("b", GOLD),
            task("c", GOLD, ambiguous=True),
            task("d", spec(video={"fps": 30})),
            task("e", GOLD),
        ]
    }
    assert [applicable(t) for t in tasks.values()] == [True, True, False, False, True]
    eps = {
        "a": {"emitted_spec": GOLD},
        "b": {"emitted_spec": spec(container="webm")},
        "e": {"emitted_spec": None},
        "c": {"emitted_spec": None},
    }
    s = summarize(tasks, eps)
    assert (s["n"], s["errors"]) == (
        3,
        2,
    )  # c is not applicable; e (no spec) stays in the denominator as an error
    assert s["by_field"]["no_spec"] == 1 and s["by_field"]["container"] == 1
