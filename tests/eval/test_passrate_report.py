from eval.passrate_report import analyse, render


def _task(i, fams, diff=1, amb=False, uns=False):
    return {"id": f"t{i}", "families": fams, "difficulty": diff, "split": "train",
            "flags": {"ambiguous": amb, "unsupported": uns}}  # fmt: skip


def test_groups_count_in_band_share_and_separate_sft_seen_tasks():
    tasks = [_task(0, ["F1"]), _task(1, ["F1", "F4"], 2), _task(2, []), _task(3, ["F6"], uns=True)]
    reasons = ["in_band", "too_easy", "too_hard", "in_band"]
    table = {"meta": {"k": 8, "band": [0.2, 0.8], "temperature": 1.0, "model": "m"},
             "tasks": {f"t{i}": {"reason": r} for i, r in enumerate(reasons)}}  # fmt: skip
    g = analyse(table, tasks, sft_ids={"t0", "t1"})
    assert g["ALL"]["n"] == 4 and g["ALL"]["in_band"] == 2 and g["ALL"]["share_in_band"] == 0.5
    assert g["families: 2"]["too_easy"] == 1 and g["involves F1"]["n"] == 2
    assert g["kind: unsupported"]["in_band"] == 1 and "families: 3" not in g
    assert g["in M1's SFT data"]["n"] == 2 and g["NOT in M1's SFT data"]["n"] == 2
    assert "| ALL | 4 | 2 |" in render(g, table["meta"])
