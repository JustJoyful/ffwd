import pytest

from training.env import chat_template as ct
from training.sft.dataset import IGNORE, build_examples, mix, stats, validation_split


@pytest.fixture(scope="module")
def tok():
    pytest.importorskip("transformers")
    from transformers import AutoTokenizer

    try:
        return ct.install(AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B", local_files_only=True))
    except OSError:
        pytest.skip("Qwen3 tokenizer not in the local HF cache")


def traj(
    task_id, fam="F1", reply='{"action": "finish", "outputs": ["out1"], "note": "ok"}', pad=""
):
    return {
        "task_id": task_id, "families": [fam],
        "messages": [
            {"role": "system", "content": "SYS" + pad}, {"role": "user", "content": "U"},
            {"role": "assistant", "content": '{"action": "run"}'}, {"role": "user", "content": '{"run_ok": true}'},
            {"role": "assistant", "content": reply}, {"role": "user", "content": '{"ended": "finish"}'},
        ],
    }  # fmt: skip


def test_labels_are_masked_outside_assistant_actions_and_include_im_end(tok):
    ex, st = build_examples([traj("a")], tok, max_len=512)
    e = ex[0]
    trained = [t for t in e["labels"] if t != IGNORE]
    assert (
        tok.decode(trained)
        == '{"action": "run"}<|im_end|>{"action": "finish", "outputs": ["out1"], "note": "ok"}<|im_end|>'
    )
    assert len(e["input_ids"]) == len(e["labels"]) and st["kept"] == 1
    assert e["labels"][0] == IGNORE  # the prompt is never trained on


def test_overlong_examples_are_dropped_and_counted_and_duplicates_removed(tok):
    ex, st = build_examples([traj("a"), traj("a"), traj("b", pad="x " * 600)], tok, max_len=300)
    assert (
        [e["task_id"] for e in ex] == ["a"]
        and st["dropped_too_long"] == 1
        and st["duplicates"] == 1
    )


def _ex(task_id, fam):
    return {"task_id": task_id, "family": fam, "input_ids": [1], "labels": [1]}


def test_rejection_samples_are_capped_and_families_are_capped():
    teacher = [_ex(f"t{i}", "F1" if i < 8 else "F2") for i in range(10)]
    rejection = [_ex(f"r{i}", "F9") for i in range(50)]
    out = mix(teacher, rejection, per_family_cap=0.5, rejection_share_max=0.2, seed=1)
    rej = [e for e in out if e["task_id"].startswith("r")]
    assert len(rej) <= 3  # 20% of the mix
    assert (
        max(sum(e["family"] == f for e in out) for f in ("F1", "F2", "F9"))
        <= int(0.5 * (10 + 3)) + 1
    )
    assert out == mix(
        teacher, rejection, per_family_cap=0.5, rejection_share_max=0.2, seed=1
    )  # deterministic


def test_validation_holds_out_whole_contents():
    exs = [_ex(f"t{i}-{s}", "F1") for i in range(400) for s in range(3)]
    keys = {e["task_id"]: f"content-{e['task_id'].split('-')[0]}" for e in exs}
    train, val = validation_split(exs, keys, fraction=0.1)
    assert {keys[e["task_id"]] for e in train}.isdisjoint({keys[e["task_id"]] for e in val})
    assert 0.03 < len(val) / len(exs) < 0.2


def test_stats_counts_trained_tokens():
    s = stats([{"task_id": "x", "family": "F1", "input_ids": [1, 2, 3], "labels": [IGNORE, 2, 3]}])
    assert s["trained_tokens"] == 2 and s["examples"] == 1


def test_oracle_share_is_capped_tagged_and_the_cap_can_be_lifted_explicitly():
    teacher = [_ex(f"t{i}", f"F{i % 4}") for i in range(70)]
    oracle = [_ex(f"o{i}", f"F{i % 4}") for i in range(200)]
    out = mix(teacher, [], oracle=oracle, oracle_share_max=0.3, per_family_cap=1.0, seed=1)
    orc = [e for e in out if e["source"] == "oracle"]
    assert len(orc) == 30 and len(orc) / len(out) <= 0.3 + 1e-9
    assert {e["source"] for e in out if e not in orc} == {"teacher"}
    lifted = mix([], [], oracle=oracle, oracle_share_max=None, per_family_cap=1.0, seed=1)
    assert len(lifted) == 200 and {e["source"] for e in lifted} == {"oracle"}
    assert (
        mix([], [], oracle=oracle, per_family_cap=1.0, seed=1) == []
    )  # default cap with no teacher: nothing


def test_invalid_action_turns_are_removed_with_their_error_message_and_counted():
    from training.sft.dataset import drop_invalid_turns

    sysm, usr = {"role": "system", "content": "s"}, {"role": "user", "content": "{}"}
    bad = [
        {"role": "assistant", "content": '{"action": "spec"}'},
        {"role": "user", "content": '{"error": "invalid action: x"}'},
    ]
    good = [
        {"role": "assistant", "content": '{"action": "spec", "spec": {}}'},
        {"role": "user", "content": '{"spec": "confirmed"}'},
    ]
    failed_run = [
        {"role": "assistant", "content": '{"action": "run"}'},
        {"role": "user", "content": '{"run_ok": true, "checks": {"out1": {"passed": false}}}'},
    ]
    msgs, n = drop_invalid_turns([sysm, usr, *bad, *good, *failed_run])
    assert n == 1 and msgs == [
        sysm,
        usr,
        *good,
        *failed_run,
    ]  # a failed CHECK is a recovery worth keeping
    assert drop_invalid_turns([sysm, usr, *good]) == ([sysm, usr, *good], 0)
