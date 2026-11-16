import json

from eval.dev_summary import summarize


def test_table_has_overall_and_by_difficulty_rows(tmp_path):
    d = tmp_path / "run"
    d.mkdir()
    rows = [
        {"task_id": f"t{i}", "success": i % 2 == 0, "difficulty": 1 + i % 2, "end_reason": "finish",
         "flags": {"ambiguous": i == 3, "unsupported": i == 4}}
        for i in range(10)
    ]  # fmt: skip
    (d / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    text = summarize({"B0": d}, "t")
    assert (
        "5/10 = 50%" in text
        and "1 family" in text
        and "2 families" in text
        and "End reasons" in text
    )
