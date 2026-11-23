import json

import pytest

from eval import phase1_extras as ex


def _results(root, system, rows):
    for split in ex.GENERATED_SPLITS:
        d = root / "runs" / f"{system}-{split}"
        d.mkdir(parents=True)
        (d / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def _row(success, end_reason, ambiguous=False, unsupported=False):
    return {
        "success": success,
        "end_reason": end_reason,
        "flags": {"ambiguous": ambiguous, "unsupported": unsupported},
    }


def test_taxonomy_counts_failures_by_kind_and_reason(tmp_path):
    _results(
        tmp_path,
        "M3",
        [
            _row(True, "finish"),
            _row(False, "run_budget"),
            _row(False, "unsupported", ambiguous=True),
            _row(True, "unsupported", unsupported=True),
        ],
    )
    t = ex.taxonomy(tmp_path, ["M3"])["M3"]
    # 3 splits x the 4 rows; 2 supported + 1 ambiguous + 1 unsupported per split
    assert t[("supported", "run_budget")] == [3, 6]
    assert t[("ambiguous", "unsupported")] == [3, 3]
    assert ("unsupported", "unsupported") not in t  # a success is not a failure row


def test_telemetry_summary_uses_first_and_last_window(tmp_path):
    steps = [
        {"step": i, "n_rollouts": 64, "pass_rate": i / 10, "mean_reward": 0, "invalid_action_rate": 0,
         "no_signal_group_share": 0, "runs_per_rollout": 1, "ask_rate_on_supported": 0,
         "refusal_rate_on_supported": 0}
        for i in range(1, 7)
    ]  # fmt: skip
    p = tmp_path / "telemetry.jsonl"
    p.write_text("\n".join(json.dumps(s) for s in steps))
    t = ex.telemetry_summary(p, window=2)
    assert t["pass_rate"]["first"] == pytest.approx(0.15)
    assert t["pass_rate"]["last"] == pytest.approx(0.55)
    assert "| pass_rate | 0.150 | 0.550 |" in ex.telemetry_md(t)
