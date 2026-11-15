#!/usr/bin/env bash
# Local rehearsal of the Kaggle kill-and-resume test (T5): train -> SIGKILL after a checkpoint was pushed
# -> brand-new empty working dir -> resume from the REMOTE only -> verify continuity.
# Usage: training/grpo/rehearse_resume.sh [BASE_DIR]   (default ~/.cache/ffagent-resume-rehearsal; avoid /tmp, it is RAM)
set -euo pipefail
cd "$(dirname "$0")/../.."
BASE=${1:-$HOME/.cache/ffagent-resume-rehearsal-$(date +%s)}
STEPS=6; KILL_AFTER=4
COMMON="--steps $STEPS --save-steps 2 --num-generations 2 --prompts-per-step 1 --max-new-tokens 64 --max-runs 1 --sync-dir $BASE/remote"
mkdir -p "$BASE"
export TRL_EXPERIMENTAL_SILENCE=1
echo "== session 1: train until checkpoint-$KILL_AFTER is on the remote, then SIGKILL"
uv run --group train python -m training.grpo.toy_spike $COMMON --ckpt-dir "$BASE/session1" > "$BASE/session1.log" 2>&1 &
pid=$!
until [ -d "$BASE/remote/checkpoint-$KILL_AFTER" ]; do
  kill -0 $pid 2>/dev/null || { echo "session 1 exited before checkpoint-$KILL_AFTER"; tail -5 "$BASE/session1.log"; exit 1; }
  sleep 2
done
pkill -9 -P $pid 2>/dev/null || true; kill -9 $pid 2>/dev/null || true; wait $pid 2>/dev/null || true
echo "killed. remote has: $(ls "$BASE/remote" | tr '\n' ' ')"
echo "== session 2: fresh empty dir, resume from the remote"
uv run --group train python -m training.grpo.toy_spike $COMMON --resume --ckpt-dir "$BASE/session2" > "$BASE/session2.log" 2>&1
grep "resuming from" "$BASE/session2.log"
echo "== verify"
uv run python -m training.grpo.verify_resume --ckpt-dir "$BASE/session2" --max-steps $STEPS --resumed-after $KILL_AFTER
