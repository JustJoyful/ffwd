#!/usr/bin/env bash
# Phase 0 baselines, run inside a memory-capped systemd unit (see the systemd-run call).
set -euo pipefail
cd /home/joydeep/Projects/ffmpeg-agent
UV=/home/joydeep/.local/bin/uv
R=reports/2026-11-15-phase-0
T=data/tasks/dev/spike-v0.jsonl
SERVER=data/tools/llama-b12032/llama-b12032/llama-server
for size in 0.6b 1.7b; do
  gguf=$(grep '^gguf_file' eval/configs/qwen3-$size.toml | cut -d'"' -f2)
  args=$(grep '^server_args' eval/configs/qwen3-$size.toml | cut -d'"' -f2)
  # shellcheck disable=SC2086  # $args is a flag list from the model config
  "$SERVER" $args -m "data/models/$gguf" --host 127.0.0.1 --port 8080 > "data/llama-$size.log" 2>&1 &
  pid=$!
  curl -s --retry 120 --retry-connrefused --retry-all-errors --retry-delay 1 -o /dev/null http://127.0.0.1:8080/health
  for sys in B1 B2; do
    echo "$(date +%T) start $sys-qwen3-$size"
    $UV run python -m eval.run_baseline --system $sys --model-config eval/configs/qwen3-$size.toml --tasks $T --out "$R/$sys-qwen3-$size"
  done
  kill $pid; wait $pid 2>/dev/null || true
done
echo "$(date +%T) start X1 pilot tasks 16-20"
$UV run python -m eval.run_baseline --system X1 --model-config eval/configs/deepseek-v4-flash.toml --tasks $T --out $R/X1-deepseek-flash-pilot-rest --offset 15 --limit 5 --budget-usd 0.05
echo "$(date +%T) start X1 tasks 21-50"
$UV run python -m eval.run_baseline --system X1 --model-config eval/configs/deepseek-v4-flash.toml --tasks $T --out $R/X1-deepseek-flash-rest --offset 20 --limit 30 --budget-usd 0.20
echo "$(date +%T) ALL_DONE"
