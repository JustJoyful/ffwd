import re

import pytest

from training.grpo import kaggle_grpo as kg


def remote_ns(p):
    """Exec the remote script's definitions (not main) with the given PARAMS."""
    ns = {"PARAMS": p, "__name__": "not-main"}
    exec(compile(kg.script(p), "run.py", "exec"), ns)
    return ns


@pytest.mark.parametrize("mode", kg.MODES)
def test_every_mode_generates_a_script_that_compiles(mode):
    compile(kg.script(kg.params(mode)), "run.py", "exec")


def test_no_token_or_secret_value_is_in_the_script_only_names():
    s = kg.script(kg.params("main"))
    assert not re.search(r"hf_[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}|github_pat_", s)
    assert "get_secret" in s and "HF_TOKEN" in s and "GITHUB_TOKEN" in s


def test_control_and_main_are_gated_on_the_owners_flags_and_the_pool():
    ok = dict(approved=True, control_passed=True, pool_on_origin=True)
    for mode in ("control", "main"):
        with pytest.raises(kg.GateError, match="not approved"):
            kg.check_gates(mode, **(ok | {"approved": False}))
        with pytest.raises(kg.GateError, match="pool"):
            kg.check_gates(mode, **(ok | {"pool_on_origin": False}))
    with pytest.raises(kg.GateError, match="control"):
        kg.check_gates("main", **(ok | {"control_passed": False}))
    kg.check_gates(
        "control", **(ok | {"control_passed": False})
    )  # the control does not need itself
    kg.check_gates("main", **ok)
    for mode in ("probe", "smoke"):  # never gated
        kg.check_gates(mode, approved=False, control_passed=False, pool_on_origin=False)


def test_smoke_uses_its_own_repo_and_the_t18_table_and_never_the_pool():
    p = kg.params("smoke")
    assert p["steps"] == 2 and p["save_steps"] == 1 and p["pool_ids"] is None
    assert p["hub_repo"].endswith("smoke-kaggle") and "pass_rates" in p["pass_rates"]
    a = remote_ns(p)["main_run_args"]()
    assert "--pass-rates-subset" in a and "--pool-ids" not in a and "--shuffle-rewards" not in a


def test_control_shuffles_rewards_and_main_does_not_and_each_has_its_own_repo():
    assert kg.params("main")["steps"] == 60 and kg.params("control")["steps"] == 30
    c, m = kg.params("control"), kg.params("main", steps=80)
    assert c["steps"] == 30 and c["shuffle_seed"] == 20261115 and m["shuffle_seed"] is None
    assert m["steps"] == 80 and c["hub_repo"] != m["hub_repo"]
    ac, am = remote_ns(c)["main_run_args"](), remote_ns(m)["main_run_args"]()
    assert "--shuffle-rewards 20261115" in ac and "--shuffle-rewards" not in am
    for a in (ac, am):
        assert "--pool-ids reports/2026-11-20-grpo-pool/pool-ids.txt" in a
        assert "--extra-train hard-v1" in a
        assert "--save-steps 10" in a and "--num-generations 8" in a and "--prompts-per-step 8" in a
    assert "--resume" in remote_ns(kg.params("main", resume=True))["main_run_args"]()


def test_push_saves_without_running_unless_asked(monkeypatch):
    seen = []

    class R:
        stdout = stderr = ""
        returncode = 0

    monkeypatch.setattr(kg, "kaggle", lambda *a, **k: (seen.append(a), R())[1])
    kg.push(kg.params("smoke"))
    kg.push(kg.params("smoke"), run=True)
    assert "--no-run" in seen[0] and "--no-run" not in seen[1]
    assert "--accelerator" in seen[0]  # GPU kernels still request the T4


def test_smoke_repo_is_not_the_deleted_one():
    assert kg.params("smoke")["hub_repo"] != "JustJoyful/ffmpeg-agent-ckpt-smoke"
