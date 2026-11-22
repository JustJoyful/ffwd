import json

from eval.checker_mutation import MUTANTS
from eval.passed_review import COLUMNS, last_command, row
from eval.quant_parity import decide

OK = {"b_minus_a": {"diff": 0.0}, "mcnemar_p": 1.0}
BASE = {"invalid": 0, "runs": 1.1, "nof": 0.1}


def test_shipping_rule_needs_every_condition():
    assert decide(BASE, BASE, OK)["ships"] == "Q4_K_M"
    assert decide(BASE, BASE, {"b_minus_a": {"diff": -0.03}, "mcnemar_p": 1.0})["ships"] == "Q8_0"
    assert decide(BASE, BASE, {"b_minus_a": {"diff": 0.0}, "mcnemar_p": 0.01})["ships"] == "Q8_0"
    assert decide(BASE, BASE | {"invalid": 3}, OK)["ships"] == "Q8_0"
    assert decide(BASE, BASE | {"runs": 1.16}, OK)["ships"] == "Q8_0"
    assert decide(BASE, BASE | {"nof": 0.2}, OK)["ships"] == "Q8_0"


def test_mutants_apply_only_when_the_spec_constrains_the_field():
    spec = {"container": "mp4", "video": {"width": 320, "height": None}, "audio": {"present": True}}
    ap = {k: v[0](spec, {"duration_s": 4.0}) for k, v in MUTANTS.items()}
    assert ap["truncate_half"] and ap["wrong_width"] and ap["drop_audio"]
    assert ap["wrong_container_mkv"]
    assert not ap["wrong_fps"] and not ap["louder_audio"] and not ap["rotate_180"]
    args = MUTANTS["truncate_half"][1](spec, {"duration_s": 4.0})
    assert args[:2] == ["-t", "2.0"]


def test_review_row_uses_the_last_run_and_survives_a_missing_job_dir(tmp_path):
    turns = [
        {"assistant": json.dumps({"action": "run", "args": ["-i", "a", "x"]})},
        {"assistant": json.dumps({"action": "run", "args": ["-i", "b", "y"]})},
        {"assistant": json.dumps({"action": "finish"})},
    ]
    ep = {"runs": 2, "emitted_spec": None, "turns": turns}
    assert last_command(ep) == "ffmpeg -i b y"
    task = {"id": "t1", "request": "cut it", "gold_spec": None}
    r = row(1, "test-iid", task, ep, tmp_path)
    assert set(r) == set(COLUMNS) and r["verdict"] == ""
    assert "not found" in r["output_properties"] and r["model_spec_plain"] == "(none)"
