"""Failure taxonomy for baseline episodes (Phase 0 follow-up T4).

Every FAILED episode gets exactly one category, decided from the stored transcript. The five
categories asked for, plus four honest extras for cases they don't cover:

  unparseable           no reply was ever valid JSON for an action (parse errors only)
  invalid_action        replies parsed but were schema-invalid or rejected by the allowlist validator
  refusal               gave up with `unsupported` on a task that is supported (and never ran FFmpeg)
  wrong_command         FFmpeg ran but exited with an error on the last executed run
  check_fail            FFmpeg ran fine but the output failed the gold-spec check on the last executed run
  stalled               valid actions but never ran a command (e.g. only specs / premature finish)
  missed_clarification  ambiguous task where the system did not ask first
  false_attempt         unsupported task where the system tried instead of refusing
  unknown_transcript_lost  the failure is in results but its transcript was lost (OOM kill, Phase 0)
"""

CATEGORIES = (
    "unparseable",
    "invalid_action",
    "refusal",
    "wrong_command",
    "check_fail",
    "stalled",
    "missed_clarification",
    "false_attempt",
    "unknown_transcript_lost",
)

_PARSE_ERRORS = (
    "reply is not a JSON object",
    "reply must be a JSON object",
    "extra text after the JSON object",
)


def _observations(episode: dict) -> list[dict]:
    return [t["observation"] for t in episode["turns"]]


def classify(row: dict, episode: dict | None) -> str | None:
    """Category of a failed episode, or None if it succeeded."""
    if row["success"]:
        return None
    if episode is None:
        return "unknown_transcript_lost"
    if row["flags"]["ambiguous"]:
        return "missed_clarification"
    if row["flags"]["unsupported"]:
        return "false_attempt"

    obs = _observations(episode)
    # A run observation with `rejected` set never reached FFmpeg (allowlist); the loop still counted it.
    executed = [o for o in obs if "run_ok" in o and not o.get("rejected") and "error" not in o]
    if executed:
        return "wrong_command" if not executed[-1]["run_ok"] else "check_fail"
    if episode["refused"]:
        return "refusal"
    errors = [o["error"] for o in obs if "error" in o and "run_ok" not in o]
    if any(o.get("rejected") for o in obs) or any(e.startswith("invalid action") for e in errors):
        return "invalid_action"
    if any(e.startswith(_PARSE_ERRORS) for e in errors):
        return "unparseable"
    return "stalled"
