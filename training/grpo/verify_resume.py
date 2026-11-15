"""Did a kill-and-resume really continue the run? (T5)  Deterministic checks only.

Rewards and losses are stochastic (sampling), so "the curve looks similar" proves little. What IS
deterministic after a correct resume, and wrong after a broken one:
  - steps run 1..N once each, in order: no gap, no duplicate, no restart from step 1;
  - the learning-rate schedule continues (the scheduler state came back; linear decay from lr0);
  - trainer_state.json still holds the pre-kill history (it is restored with the checkpoint).

  uv run python -m training.grpo.verify_resume --ckpt-dir /kaggle/working/ckpt --lr0 1e-5 --max-steps 10 --resumed-after 6
"""

import argparse
import json
import sys
from pathlib import Path

from training.grpo.ckpt_sync import local_latest


def verify(
    rows: list[dict],
    lr_by_step: dict[int, float],
    *,
    lr0: float,
    max_steps: int,
    resumed_after: int,
) -> dict:
    problems: list[str] = []
    steps = [r["step"] for r in rows]
    seen: set[int] = set()
    for i, s in enumerate(steps):
        if s in seen:
            problems.append(f"duplicate step {s}")
        seen.add(s)
        if i and s <= steps[i - 1]:
            problems.append(
                f"training restarted or reordered: step {s} follows step {steps[i - 1]}"
            )
    missing = sorted(set(range(1, max(steps, default=0) + 1)) - seen)
    if missing:
        problems.append(f"gap: missing steps {missing}")
    if max(steps, default=0) <= resumed_after:
        problems.append(f"no step after the resume point {resumed_after}")
    for s, lr in sorted(lr_by_step.items()):
        expected = lr0 * (1 - (s - 1) / max_steps)  # linear decay, no warmup (GRPOConfig default)
        if abs(lr - expected) > 1e-9 + 1e-6 * abs(expected):
            problems.append(
                f"learning rate at step {s} is {lr:g}, expected {expected:g} (scheduler state not restored?)"
            )
    return {"ok": not problems, "problems": problems, "steps": steps}


def load_lr(trainer_state: Path) -> dict[int, float]:
    state = json.loads(trainer_state.read_text())
    return {
        e["step"]: float(e["learning_rate"]) for e in state["log_history"] if "learning_rate" in e
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt-dir", type=Path, required=True)
    ap.add_argument("--lr0", type=float, default=1e-5)
    ap.add_argument("--max-steps", type=int, required=True)
    ap.add_argument("--resumed-after", type=int, required=True)
    a = ap.parse_args()
    rows = [
        json.loads(x)
        for x in (a.ckpt_dir / "toy_metrics.jsonl").read_text().splitlines()
        if x.strip()
    ]
    last = local_latest(a.ckpt_dir)
    if last is None:
        sys.exit("no checkpoint found to read trainer_state.json from")
    result = verify(
        rows,
        load_lr(last / "trainer_state.json"),
        lr0=a.lr0,
        max_steps=a.max_steps,
        resumed_after=a.resumed_after,
    )
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
