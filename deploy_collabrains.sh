#!/usr/bin/env bash
# Deploy CollaBrains with the AI/resource optimizations for this project's
# 4-vCPU/8GB CPU-only host (docs/deployment/ai-optimization.md). Run from the
# repo root ON THE SERVER (/opt/collabrains) after `git pull`.
#
# Idempotent: safe to re-run. Each step only changes something if it isn't
# already in the desired state.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

log() { printf '\n=== %s ===\n' "$1"; }

log "1/5: swap file (best-effort)"
# This project's known hosts are OpenVZ containers, which cannot swapon at all
# (confirmed: swapon fails with "Operation not permitted", see
# docs/deployment/ai-optimization.md) -- mem_limit on each Compose service is
# this project's actual safety net instead. Still attempted here in case this
# script ever runs on a non-OpenVZ host that supports it.
if swapon --show 2>/dev/null | grep -q .; then
  echo "swap already active, skipping"
elif [ ! -f /swapfile ]; then
  if fallocate -l 4G /swapfile 2>/dev/null && chmod 600 /swapfile && mkswap /swapfile >/dev/null; then
    if swapon /swapfile 2>/dev/null; then
      grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
      echo "4G swap file created and enabled"
    else
      echo "WARNING: swapon failed (likely an OpenVZ/container host that can't swap) -- continuing without swap, relying on Compose mem_limits instead"
      rm -f /swapfile
    fi
  else
    echo "WARNING: could not create /swapfile -- continuing without swap"
  fi
else
  echo "/swapfile exists but is not active -- leaving as-is, check manually"
fi

log "2/5: Ollama resource limits + models"
# Limits themselves live in docker-compose.yml (mem_limit/OLLAMA_NUM_PARALLEL/
# OLLAMA_MAX_LOADED_MODELS on the `ollama` service) -- version controlled, not a
# systemd override, since Ollama runs as a Compose service here, not a bare-metal
# systemd unit. No CPU cap: live-tested and reverted, see ai-optimization.md --
# it slowed qwen3:8b (the model chat_model actually needs) past this app's httpx
# timeout. chat_model stays qwen3:8b, NOT a 1.5B/3B model -- both were live-tested
# against manager_agent's tool-calling and found broken (fake/no tool calls,
# hallucinated non-English output), not just lower quality. deepseek-r1:1.5b is
# the one new light model that's actually used, by POST /manager/reason only.
docker compose --profile full up -d ollama
echo "waiting for ollama to accept connections..."
for _ in $(seq 1 30); do
  docker compose exec -T ollama ollama list >/dev/null 2>&1 && break
  sleep 2
done
for model in qwen3:8b deepseek-r1:1.5b nomic-embed-text; do
  echo "pulling $model..."
  docker compose exec -T ollama ollama pull "$model"
done

log "3/5: build API + web"
docker compose build api web

log "4/5: apply and restart"
# api runs uvicorn --reload against a bind mount, so code changes apply on
# `git pull` alone -- `up -d` here is for picking up .env/image changes, not
# for the reload itself.
docker compose up -d api ollama
docker compose exec -T web sh -c 'cd /app/apps/web && NODE_OPTIONS=--max-old-space-size=2048 npx vite build'

log "5/5: verify"
docker compose ps --format '{{.Service}} {{.State}}'
echo "--- ollama resource usage ---"
docker stats --no-stream collabrains-ollama-1
echo "--- models pulled ---"
docker compose exec -T ollama ollama list

echo
echo "Deploy done. Test endpoints with:"
echo "  curl -s -X POST http://127.0.0.1:8000/manager/ask -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{\"message\": \"hello\"}'"
echo "  curl -s -X POST http://127.0.0.1:8000/manager/reason -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{\"prompt\": \"what is 17 * 24?\"}'"
