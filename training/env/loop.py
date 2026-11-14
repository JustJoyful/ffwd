"""Python agent loop (ARCH §3.1) and episode scoring.

In training/eval the "confirmed" spec is always the task's GOLD spec (RULES §4.4): the model's own
spec is recorded for spec-accuracy metrics but never used to grade its output.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from training import config
from training.env.actions import ParseError, parse_action
from training.env.checker import check
from training.env.executor import execute, output_path_for
from training.env.probe import probe

Policy = Callable[[list[dict]], str]
EndReason = Literal["finish", "unsupported", "run_budget", "turn_budget"]

NO_MORE_INFO = "No more information is available; proceed with your best interpretation."


@dataclass
class Episode:
    task_id: str
    turns: list[dict] = field(default_factory=list)
    emitted_spec: dict | None = None
    runs: int = 0
    invalid_turns: int = 0
    asked: bool = False  # asked a question before any run
    refused: bool = False
    last_check: dict | None = None
    end_reason: EndReason = "turn_budget"


def system_prompt() -> str:
    return (config.PROTOCOL_DIR / "prompts" / "system-v0.txt").read_text()


def _first_user_message(task: dict, probes: dict[str, dict]) -> str:
    out_ids = [o["id"] for o in task["gold_spec"]["outputs"]] if task["gold_spec"] else ["out1"]
    return json.dumps(
        {
            "request": task["request"],
            "inputs": [{"id": cid, "probe": probes[cid]} for cid in task["inputs"]],
            "outputs": out_ids,
        }
    )


def _do_run(
    action: dict,
    task: dict,
    ep: Episode,
    corpus: dict[str, Path],
    job_dir: Path,
    probes: dict[str, dict],
) -> dict:
    gold = {o["id"]: o for o in task["gold_spec"]["outputs"]}
    run_dir = job_dir / f"run{ep.runs}"
    result = execute(
        action,
        input_paths={cid: corpus[cid] for cid in task["inputs"]},
        output_paths={oid: output_path_for(run_dir, spec) for oid, spec in gold.items()},
    )
    if not result.ok:
        ep.last_check = {"passed": False, "outputs": {}}
        return {"run_ok": False, "rejected": result.rejected, "stderr_tail": result.stderr_tail}
    input_probe = probes[task["inputs"][0]]
    checks = {
        oid: check(gold[oid], path, input_probe=input_probe, run_args=action["args"])
        for oid, path in result.outputs.items()
    }
    # Pass only when every gold output was produced in this run and passed.
    ep.last_check = {
        "passed": set(checks) == set(gold) and all(c["passed"] for c in checks.values()),
        "outputs": checks,
    }
    return {
        "run_ok": True,
        "checks": {
            oid: {
                "passed": c["passed"],
                "error": c["error"],
                "failed": [x for x in c["checks"] if not x["ok"]],
            }
            for oid, c in checks.items()
        },
        "missing_outputs": sorted(set(gold) - set(checks)),
    }


def run_episode(
    task: dict,
    policy: Policy,
    *,
    corpus: dict[str, Path],
    job_dir: Path,
    max_runs: int = config.MAX_RUNS_PER_JOB,
) -> Episode:
    ep = Episode(task_id=task["id"])
    probes = {cid: probe(corpus[cid]) for cid in task["inputs"]}
    messages = [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": _first_user_message(task, probes)},
    ]
    asks = 0
    while len(ep.turns) < config.MAX_TURNS_PER_JOB:
        reply = policy(messages)
        action = parse_action(reply)
        done = False
        if isinstance(action, ParseError):
            ep.invalid_turns += 1
            obs: dict = {"error": action.message}
        elif action["action"] == "spec":
            ep.emitted_spec = action["spec"]
            obs = {"spec": "confirmed"}
        elif action["action"] == "ask_user":
            asks += 1
            if asks > config.MAX_ASK_USER:
                ep.invalid_turns += 1
                obs = {"error": "only one question is allowed per job"}
            else:
                ep.asked = ep.asked or ep.runs == 0
                obs = {"answer": task.get("clarification") or NO_MORE_INFO}
        elif action["action"] == "unsupported":
            ep.refused, ep.end_reason, done = True, "unsupported", True
            obs = {"ended": "unsupported"}
        elif action["action"] == "finish":
            if ep.last_check and ep.last_check["passed"]:
                ep.end_reason, done = "finish", True
                obs = {"ended": "finish"}
            else:
                obs = {"error": "finish requires a passing check"}
        else:  # run
            if ep.runs >= max_runs:
                ep.end_reason, done = "run_budget", True
                obs = {"error": "run budget exhausted"}
            else:
                ep.runs += 1
                if task["gold_spec"] is None:
                    # Ambiguous/unsupported tasks have no gradable output: count the run, don't execute.
                    ep.last_check = {"passed": False, "outputs": {}}
                    obs = {"run_ok": False, "error": "this request has no executable outputs"}
                else:
                    obs = _do_run(action, task, ep, corpus, job_dir, probes)
                if ep.runs >= max_runs and not ep.last_check["passed"]:
                    ep.end_reason, done = "run_budget", True
        ep.turns.append({"assistant": reply, "observation": obs})
        messages += [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": json.dumps(obs)},
        ]
        if done:
            break
    return ep


def score(task: dict, ep: Episode) -> bool:
    """Task success (EVALUATION §4.1). Ambiguous: asked before running. Unsupported: refused
    without running. Otherwise: the last run's outputs passed the gold spec."""
    if task["flags"]["ambiguous"]:
        return ep.asked
    if task["flags"]["unsupported"]:
        return ep.refused and ep.runs == 0
    return bool(ep.last_check and ep.last_check["passed"])
