#!/usr/bin/env bash
# Phase 0 follow-up T4: fair base-model baselines (small-model prompt + schema-constrained decoding).
# Run inside a memory-capped unit:  systemd-run --user --wait -p MemoryMax=4G -p MemorySwapMax=1G eval/run_fair_baselines.sh
set -euo pipefail
cd "$(dirname "$0")/.."
UV=${UV:-uv}
R=${R:-reports/2026-11-16-phase0-followups}
T=data/tasks/dev/spike-v0.jsonl
SERVER=data/tools/llama-b12032/llama-b12032/llama-server
for size in 0.6b 1.7b; do
  gguf=$(grep '^gguf_file' eval/configs/qwen3-$size-fair.toml | cut -d'"' -f2)
  args=$(grep '^server_args' eval/configs/qwen3-$size-fair.toml | cut -d'"' -f2)
  # shellcheck disable=SC2086  # $args is a flag list from the model config
  "$SERVER" $args -m "data/models/$gguf" --host 127.0.0.1 --port 8080 > "data/llama-$size-fair.log" 2>&1 &
  pid=$!
  curl -s --retry 120 --retry-connrefused --retry-all-errors --retry-delay 1 -o /dev/null http://127.0.0.1:8080/health
  for sys in B1 B2; do
    echo "$(date +%T) start $sys-qwen3-$size-fair"
    $UV run python -m eval.run_baseline --system $sys --model-config eval/configs/qwen3-$size-fair.toml --tasks $T --out "$R/$sys-qwen3-$size-fair"
  done
  kill $pid; wait $pid 2>/dev/null || true
done
echo "$(date +%T) ALL_DONE"
