"""One interactive job: probe -> model proposes a SPEC -> the person confirms it -> run/check until it passes.

Differences from the training loop (D-008): there is no gold spec. The spec the person CONFIRMED is the contract the
checker uses; the model never grades itself. Success is reported only when a check passed (RULES §8.1).
"""

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from training import config
from training.env.actions import ParseError, parse_action
from training.env.chat_template import render
from training.env.checker import check
from training.env.describe_spec import describe_spec
from training.env.executor import execute, output_path_for
from training.env.loop import Policy
from training.env.probe import probe

INPUT_ID, OUTPUT_ID = "in1", "out1"
MAX_SPEC_REVISIONS = 2


class ContextFull(RuntimeError):
    """The next prompt plus the reply budget does not fit in n_ctx: the job ends as not done, never truncated (D-051)."""


def context_guard(
    policy: Policy, count_tokens: Callable[[str], int], n_ctx: int, max_tokens: int
) -> Policy:
    """Refuse a model call whose rendered prompt + reply budget would not fit in the context window."""

    def guarded(messages: list[dict]) -> str:
        if count_tokens(render(messages, add_generation_prompt=True)) + max_tokens > n_ctx:
            raise ContextFull
        return policy(messages)

    return guarded


@dataclass
class JobResult:
    ok: bool
    message: str
    output: Path | None = None
    spec: dict | None = None
    runs: int = 0
    check: dict | None = None
    exit_code: int = 1


def _unique(dest: Path) -> Path:
    n, cand = 1, dest
    while cand.exists():  # outputs never overwrite anything, least of all the input (RULES §1.5)
        cand = dest.with_name(f"{dest.stem}_{n}{dest.suffix}")
        n += 1
    return cand


def run_job(
    request: str,
    input_path: Path,
    policy: Policy,
    *,
    out_dir: Path,
    system_prompt: str,
    confirm: Callable[[list[str]], bool | str],
    ask: Callable[[str], str],
    say: Callable[[str], None] = print,
    max_runs: int = config.MAX_RUNS_PER_JOB,
) -> JobResult:
    p = probe(input_path)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps({"request": request, "inputs": [{"id": INPUT_ID, "probe": p}], "outputs": [OUTPUT_ID]})},
    ]  # fmt: skip
    work = out_dir / ".ffmpeg-agent-jobs" / f"job-{abs(hash((request, str(input_path)))) % 10**8}"
    confirmed: dict | None = None
    runs = revisions = asks = invalid = 0
    last_check: dict | None = None
    last_out: Path | None = None
    last_failure = ""  # shown to the person: why the last run did not pass
    for _ in range(config.MAX_TURNS_PER_JOB):
        try:
            reply = policy(messages)
        except ContextFull:
            return JobResult(
                False,
                "Too long: the conversation no longer fits in the model's context window, so I "
                "stopped. Nothing was claimed as done.",
                spec=confirmed,
                runs=runs,
                check=last_check,
                exit_code=6,
            )
        action = parse_action(reply)
        if isinstance(action, ParseError):
            invalid += 1
            obs: dict = {"error": action.message}
        elif action["action"] == "spec":
            answer = confirm(describe_spec(action["spec"]))
            if answer is True:
                confirmed, obs = action["spec"], {"spec": "confirmed"}
            elif revisions >= MAX_SPEC_REVISIONS:
                return JobResult(False, "No spec was confirmed, so nothing was run.", exit_code=3)
            else:
                revisions += 1
                obs = {
                    "error": f"the user did not confirm this spec: {answer or 'please revise it'}"
                }
        elif action["action"] == "ask_user":
            asks += 1
            obs = (
                {"error": "only one question is allowed"}
                if asks > config.MAX_ASK_USER
                else {"answer": ask(action["question"])}
            )
        elif action["action"] == "unsupported":
            return JobResult(
                False, f"This is not something I can do: {action['reason']}", exit_code=2
            )
        elif action["action"] == "finish":
            if last_check and last_check["passed"] and last_out:
                dest = (
                    _unique(out_dir / f"{input_path.stem}_edited{last_out.suffix}")
                    if last_out.is_file()
                    else _unique(out_dir / f"{input_path.stem}_frames")
                )
                shutil.move(str(last_out), str(dest))
                return JobResult(
                    True,
                    f"Done: {dest}",
                    output=dest,
                    spec=confirmed,
                    runs=runs,
                    check=last_check,
                    exit_code=0,
                )
            obs = {"error": "finish requires a passing check"}
        elif confirmed is None:
            invalid += 1
            obs = {"error": "emit a spec action first; a run before a spec is rejected"}
        elif runs >= max_runs:
            break
        else:
            runs += 1
            out_spec = confirmed["outputs"][0] | {"id": OUTPUT_ID}
            run_dir = work / f"run{runs}"
            res = execute(
                action,
                input_paths={INPUT_ID: input_path},
                output_paths={OUTPUT_ID: output_path_for(run_dir, out_spec)},
                sandbox="auto",
            )
            if not res.ok:
                last_check = {"passed": False}
                tail = (res.stderr_tail or "").strip().splitlines()
                last_failure = (
                    f"the last run failed: {res.rejected or (tail[-1] if tail else 'no output')}"
                )
                obs = {"run_ok": False, "rejected": res.rejected, "stderr_tail": res.stderr_tail}
            else:
                last_out = res.outputs[OUTPUT_ID]
                last_check = check(
                    out_spec,
                    last_out,
                    input_probe=p,
                    run_args=action["args"],
                    input_probes=[p],
                    input_paths=[input_path],
                )
                failed = [c for c in last_check["checks"] if not c["ok"]]
                names = ", ".join(c["field"] for c in failed) or str(last_check["error"])
                last_failure = (
                    "" if last_check["passed"] else f"the last run failed the check ({names})"
                )
                say(
                    f"  run {runs}: "
                    + ("check passed" if last_check["passed"] else f"check failed ({names})")
                )
                obs = {
                    "run_ok": True,
                    "checks": {
                        OUTPUT_ID: {
                            "passed": last_check["passed"],
                            "error": last_check["error"],
                            "failed": failed,
                        }
                    },
                }
        messages += [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": json.dumps(obs)},
        ]
    why = "the run budget was used up" if runs >= max_runs else "the model did not finish"
    return JobResult(
        False,
        f"Could not produce a verified result: {why}"
        + (f"; {last_failure}" if last_failure else "")
        + ". Nothing was claimed as done.",
        spec=confirmed,
        runs=runs,
        check=last_check,
        exit_code=1,
    )
