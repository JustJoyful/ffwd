import json

from eval.spotcheck_view import files_of, flags, render, run_args

COPY = ["-ss", "2", "-i", "{in:a}", "-c", "copy", "{out:out1}"]
ENCODE = ["-i", "{in:a}", "-vf", "scale=640:-2", "-c:v", "libx264", "{out:out1}"]


def task(ref, ambiguous=False, unsupported=False):
    return {
        "request": "r",
        "flags": {"ambiguous": ambiguous, "unsupported": unsupported},
        "reference_runs": [{"args": ref}],
    }


def rec(args=None, reward=1.1, passed=True, duration=4.0, asked=False, refused=False, invalid=0):
    turns = []
    if args:
        action = json.dumps({"action": "run", "args": args})
        turns = [{"assistant": action, "observation": {"run_ok": True}}]
    check = {"outputs": {"out1": {"passed": passed, "measurements": {"duration_s": duration}}}}
    ep = {
        "task_id": "t",
        "turns": turns,
        "runs": len(turns),
        "invalid_turns": invalid,
        "asked": asked,
        "refused": refused,
        "last_check": check,
        "end_reason": "finish",
    }
    return {"reward": reward, "terms": {"pass": 1.0 if passed else 0.0}, "episode": ep}


def test_clean_transcripts_have_no_flags():
    assert flags(rec(COPY), task(COPY)) == []
    assert flags(rec(ENCODE), task(ENCODE)) == []


def test_stream_copy_where_the_reference_needs_a_re_encode_is_flagged_only_when_it_passed():
    assert flags(rec(COPY), task(ENCODE)) == ["copy_where_reencode_required"]
    assert flags(rec(COPY, passed=False, reward=0.2), task(ENCODE)) == []


def test_dodging_tiny_outputs_pass_without_run_and_invalid_heavy():
    assert "ask_or_refuse_rewarded" in flags(rec(None, asked=True, reward=1.0), task(COPY))
    ambiguous = flags(rec(None, asked=True, reward=1.0), task(COPY, ambiguous=True))
    assert "ask_or_refuse_rewarded" not in ambiguous  # asking on an ambiguous task is correct
    assert "tiny_output" in flags(rec(ENCODE, duration=0.1), task(ENCODE))
    assert "tiny_output" in flags(rec(ENCODE, duration=None), task(ENCODE))
    assert "pass_without_run" in flags(rec(None, reward=1.0), task(COPY))
    assert "invalid_heavy" in flags(rec(ENCODE, invalid=3), task(ENCODE))


def test_render_shows_the_request_commands_checks_and_flags_and_files_are_found(tmp_path):
    out = render(rec(COPY), task(ENCODE))
    assert "request: r" in out and "-c copy" in out and "FLAGS: copy_where_reencode_required" in out
    assert run_args(rec(COPY)["episode"]) == [COPY]
    d = tmp_path / "spotcheck"
    d.mkdir()
    for n in (20, 10):
        (d / f"step-{n}.jsonl").write_text("{}\n")
    assert [p.name for p in files_of(tmp_path)] == ["step-10.jsonl", "step-20.jsonl"]
