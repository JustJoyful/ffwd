from eval.copy_eligible_counts import copy_eligible, counts, graded

COPY = ["-ss", "2", "-i", "{in:a}", "-c", "copy", "{out:out1}"]
ENCODE = ["-i", "{in:a}", "-vf", "scale=640:-2", "-c:v", "libx264", "{out:out1}"]


def t(i, args=None, ambiguous=False, unsupported=False):
    return {
        "id": i,
        "flags": {"ambiguous": ambiguous, "unsupported": unsupported},
        "reference_runs": [{"args": args}] if args else [],
    }


def test_copy_eligible_needs_a_graded_task_whose_reference_is_stream_copy_only():
    assert copy_eligible(t("a", COPY)) and not copy_eligible(t("b", ENCODE))
    assert not copy_eligible(t("c", COPY, ambiguous=True))  # no gradable run
    assert not copy_eligible(t("d", COPY, unsupported=True))
    assert not graded(t("e")) and not copy_eligible(t("e"))  # no reference run


def test_counts_and_the_id_restriction():
    ts = [t("a", COPY), t("b", ENCODE), t("c", COPY, ambiguous=True), t("d", COPY)]
    assert counts(ts) == {"tasks": 4, "graded": 3, "copy_eligible": 2}
    assert counts(ts, {"a", "b"}) == {"tasks": 2, "graded": 2, "copy_eligible": 1}


def test_counts_hold_no_task_content():
    c = counts([t("secret-id", COPY)])
    assert set(c) == {"tasks", "graded", "copy_eligible"}
    assert all(isinstance(v, int) for v in c.values())
