"""The browser-row analysis (eval/browser_row_report.py) on DEV data only: the Q5_K_M browser dev run against the native Q8_0 dev run."""

import json

import pytest

from eval import browser_row_report as brr
from eval.final_report import load
from eval.hf_parity import sample_ids
from eval.quant_parity import SEED, N
from training import config
from training.taskgen.loader import load_tasks

BROWSER_RUN = config.REPO_ROOT / "reports" / "2026-11-23-browser-gguf" / "M3-browser-q5km-gpu-kvq80"
Q8_RUN = config.REPO_ROOT / "reports" / "2026-11-22-m3-ckpt60-dev" / "grpo-m3-ckpt60-q8"

pytestmark = pytest.mark.skipif(
    not (BROWSER_RUN.exists() and Q8_RUN.exists()), reason="dev run directories not present"
)


@pytest.fixture(scope="module")
def dev():
    all_tasks = load_tasks("dev", "dev-eval")
    ids = set(sample_ids(all_tasks, N, SEED))
    tasks = {t["id"]: t for t in all_tasks if t["id"] in ids}
    only = lambda pair: tuple({k: v for k, v in d.items() if k in ids} for d in pair)  # noqa: E731
    # the dev sample stands in for one split; the code path is the same as for the three test splits
    loaded = {
        brr.BROWSER: {"test-iid": only(load(BROWSER_RUN))},
        brr.BASE: {"test-iid": only(load(Q8_RUN))},
    }
    return loaded, {"test-iid": tasks}


def test_analysis_on_dev_data(dev):
    loaded, tasks_by_split = dev
    r = brr.analyse(loaded, tasks_by_split)
    assert r["splits"] == ["test-iid"]
    assert (
        r["systems"][brr.BROWSER]["test-iid"]["k"] == 97
        and r["systems"][brr.BASE]["test-iid"]["k"] == 97
    )
    p = r["primary"]
    assert p["n"] == 100 and abs(p["diff"]) < 1e-9  # 97 and 97
    assert p["guard"]["margin"] == 0.02 and p["guard"]["lower_bound_975"] == p["ci95"][0]
    assert isinstance(p["guard"]["shown"], bool)
    assert "p_value" not in json.dumps(r)  # no confirmatory claim for this row
    assert r["context_rule_endings"] == {"test-iid": 0}
    assert r["invalid_action_episodes"][brr.BROWSER]["test-iid"] == 0


def test_render_says_descriptive_and_states_the_guard(dev):
    text = brr.render(brr.analyse(*dev))
    assert "extra row" in text and "No p-values" in text and "Guard" in text and "headline" in text


def test_a_missing_task_is_a_denominator_bug(dev):
    loaded, tasks_by_split = dev
    res, eps = loaded[brr.BROWSER]["test-iid"]
    short = {
        brr.BROWSER: {"test-iid": (dict(list(res.items())[1:]), eps)},
        brr.BASE: loaded[brr.BASE],
    }
    with pytest.raises(ValueError, match="do not cover"):
        brr.analyse(short, tasks_by_split)
