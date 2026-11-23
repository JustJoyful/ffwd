import json

import pytest

from eval.browser_parity import turn_stats


def row(wall, n_msgs, prompt_n, cache_n, gen_n, prompt_ms, gen_ms, ptok=1500):
    return {
        "n_messages": n_msgs,
        "finish_reason": "stop",
        "wall_ms": wall,
        "usage": {"prompt_tokens": ptok, "total_tokens": ptok + gen_n},
        "timings": {"prompt_n": prompt_n, "cache_n": cache_n, "predicted_n": gen_n, "prompt_ms": prompt_ms, "predicted_ms": gen_ms},  # fmt: skip
    }


def test_turn_stats_median_and_separate_rates(tmp_path):
    rows = [
        row(2000, 2, 1400, 0, 100, 1000, 1000),
        row(4000, 4, 100, 1400, 100, 100, 1000, ptok=1600),
        row(9000, 6, 100, 1500, 50, 100, 500, ptok=1700),
    ]
    p = tmp_path / "turns.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    s = turn_stats(p)
    assert s["wall_ms"]["median"] == 4000 and s["wall_ms"]["max"] == 9000
    assert s["prompt_tok_s"] == pytest.approx(
        1600 / 1200 * 1000
    )  # processed tokens only; cached ones cost nothing
    assert s["gen_tok_s"] == pytest.approx(250 / 2500 * 1000)
    assert s["max_prompt_tokens"] == 1700 and s["first_turn_wall_ms_median"] == 2000
