#!/usr/bin/env bash
set -euo pipefail

# Collects a simple environment metadata package after a run.
# This script does not remove files or change system settings.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCENARIO="${SCENARIO:-manual}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT_DIR/results}"
LOGS_DIR="${LOGS_DIR:-$RESULTS_DIR/logs}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$LOGS_DIR/collection-${SCENARIO}-${RUN_ID}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://127.0.0.1:9090}"

mkdir -p "$OUT_DIR"

{
  echo "run_id=$RUN_ID"
  echo "scenario=$SCENARIO"
  echo "timestamp_utc=$(date -u --iso-8601=seconds)"
  echo "hostname=$(hostname)"
  echo "kernel=$(uname -a)"
} > "$OUT_DIR/metadata.txt"

if [[ -f /etc/os-release ]]; then
  cp /etc/os-release "$OUT_DIR/os-release.txt"
fi

if command -v k6 >/dev/null 2>&1; then
  k6 version > "$OUT_DIR/k6-version.txt" 2>&1 || true
fi

if command -v nginx >/dev/null 2>&1; then
  nginx -v > "$OUT_DIR/nginx-version.txt" 2>&1 || true
fi

if command -v docker >/dev/null 2>&1; then
  docker version > "$OUT_DIR/docker-version.txt" 2>&1 || true
  docker info > "$OUT_DIR/docker-info.txt" 2>&1 || true
  docker ps > "$OUT_DIR/docker-ps.txt" 2>&1 || true
  docker stats --no-stream > "$OUT_DIR/docker-stats.txt" 2>&1 || true
fi

if command -v curl >/dev/null 2>&1; then
  curl -fsS "$PROMETHEUS_URL/api/v1/targets" > "$OUT_DIR/prometheus-targets.json" 2>/dev/null || true
fi

echo "Collection completed in $OUT_DIR"
