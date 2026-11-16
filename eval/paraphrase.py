"""Paraphrase the dev tasks once with DeepSeek (budget-guarded) to test wording robustness.

uv run python -m eval.paraphrase --tasks data/tasks/dev/spike-v0.jsonl \
    --out-tasks data/tasks/dev/spike-v0-para.jsonl --log reports/<dir>/paraphrase-log.jsonl --budget-usd 0.02

Dev tasks only. A paraphrase is kept only if its digits equal the original's AND a second call, shown
the gold spec, says the meaning is unchanged. Nothing is regenerated (no selection on B0/X1 results).
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from training import config
from training.policies import ChatPolicy
from training.teacher.budget import BudgetGuard

NUM = re.compile(r"\d+(?::\d+)*(?:\.\d+)?")

PARA_SYSTEM = (
    "Reword the user's video-editing request the way a different person would phrase it: different "
    "words and sentence shape, same casual register. Keep every number, time and unit exactly as digits "
    "(e.g. 0:12, 720p, 3 MB, -16 LUFS). Do not add or drop any requirement, and do not make a vague "
    "request more specific. Reply with the reworded request only."
)
JUDGE_SYSTEM = (
    "You check paraphrases of video-editing requests. Given the original, the paraphrase and the exact "
    "spec the original stands for, answer YES only if someone reading the paraphrase would want exactly "
    "that spec: same operations and values, nothing added or removed, and an ambiguous or unsupported "
    "request is still ambiguous or unsupported. Otherwise answer NO. Reply YES or NO only."
)


def numbers(text: str) -> Counter:
    return Counter(NUM.findall(text))


def clean(raw: str) -> str:
    return raw.strip().splitlines()[0].strip().strip("\"'`").strip() if raw.strip() else ""


def judge_prompt(task: dict, paraphrase: str) -> str:
    return json.dumps(
        {
            "original": task["request"],
            "paraphrase": paraphrase,
            "spec": task["gold_spec"],
            "flags": task["flags"],
        }
    )


def paraphrase_tasks(tasks: list[dict], write, judge) -> tuple[list[dict], list[dict]]:
    """(kept tasks, log rows for every task). write/judge: callables str -> str."""
    kept, log = [], []
    for t in tasks:
        text = clean(write(t["request"]))
        reason = None
        if not text or text.lower() == t["request"].lower():
            reason = "empty or unchanged"
        elif numbers(text) != numbers(t["request"]):
            reason = "digits differ"
        else:
            verdict = judge(judge_prompt(t, text)).strip().upper()
            if not verdict.startswith("YES"):
                reason = f"judge: {verdict[:20] or 'empty'}"
        log.append(
            {"task_id": t["id"], "original": t["request"], "paraphrase": text, "dropped": reason}
        )
        if reason is None:
            kept.append(
                t
                | {
                    "request": text,
                    "source": "spike-v0-paraphrase",
                    "original_request": t["request"],
                }
            )
    return kept, log


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, required=True)
    ap.add_argument("--out-tasks", type=Path, required=True)
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--budget-usd", type=float, required=True)
    ap.add_argument("--run-id", default="paraphrase-v0")
    a = ap.parse_args(argv)
    for p in (a.out_tasks, a.log):
        if p.exists():
            sys.exit(f"refusing to overwrite {p}")
    tasks = [json.loads(x) for x in a.tasks.read_text().splitlines()]
    if any(t["split"] != "dev" for t in tasks):
        sys.exit("paraphrasing is for dev tasks only")  # RULES: test data is sacred
    guard = BudgetGuard(config.LEDGER_PATH, config.BUDGET_LIFETIME_USD, a.budget_usd, a.run_id)
    body = {"thinking": {"type": "disabled"}}

    def policy(temperature: float, max_tokens: int) -> ChatPolicy:
        return ChatPolicy(
            config.DEEPSEEK_BASE_URL,
            config.DEEPSEEK_MODEL_ID or "",
            config.DEEPSEEK_API_KEY_ENV,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=body,
            guard=guard,
        )

    writer, judge = policy(0.7, 80), policy(0.0, 5)  # judge is deterministic
    kept, log = paraphrase_tasks(
        tasks,
        lambda r: writer(
            [{"role": "system", "content": PARA_SYSTEM}, {"role": "user", "content": r}]
        ),
        lambda p: judge(
            [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": p}]
        ),
    )
    a.out_tasks.write_text("".join(json.dumps(t) + "\n" for t in kept))
    a.log.write_text("".join(json.dumps(r) + "\n" for r in log))
    print(f"kept {len(kept)}/{len(tasks)}; spent ${guard.spent(run_only=True):.4f}")


if __name__ == "__main__":
    main()
