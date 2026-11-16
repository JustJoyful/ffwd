#!/usr/bin/env bash
# Phase 1 dev baselines with the v1 protocol (free, local). Run in a capped unit:
#   systemd-run --user --wait -p MemoryMax=4G -p MemorySwapMax=1G eval/run_dev_baselines_v1.sh
set -euo pipefail
cd "$(dirname "$0")/.."
R=${R:-reports/2026-11-16-phase1-dev-baselines}
SERVER=data/tools/llama-b12032/llama-b12032/llama-server
cfg=eval/configs/qwen3-0.6b-v1.toml
gguf=$(grep '^gguf_file' $cfg | cut -d'"' -f2)
args=$(grep '^server_args' $cfg | cut -d'"' -f2)
# shellcheck disable=SC2086
"$SERVER" $args -m "data/models/$gguf" --host 127.0.0.1 --port 8080 > data/llama-v1-dev.log 2>&1 &
pid=$!
curl -s --retry 120 --retry-connrefused --retry-all-errors --retry-delay 1 -o /dev/null http://127.0.0.1:8080/health
uv run python -m eval.run_baseline --system B2 --model-config $cfg --tasks data/tasks/dev/v1.jsonl --out "$R/B2-qwen3-0.6b-dev-v1"
kill $pid; wait $pid 2>/dev/null || true
echo "$(date +%T) ALL_DONE"
