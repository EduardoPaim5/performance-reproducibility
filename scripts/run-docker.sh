#!/usr/bin/env bash
set -euo pipefail

# C2: runs Nginx in local Docker with Prometheus, Node Exporter, and cAdvisor.
# The default Nginx port is 8080 on the local host.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose.yml"
TARGET_URL="${TARGET_URL:-http://127.0.0.1:8080/health}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker was not found in PATH."
  exit 1
fi

docker compose -f "$COMPOSE_FILE" up -d --build

echo "C2 started."
echo "Nginx:      http://127.0.0.1:8080/"
echo "Prometheus: http://127.0.0.1:9090/"
echo "cAdvisor:   http://127.0.0.1:8081/"

if command -v curl >/dev/null 2>&1; then
  echo "Checking endpoint: $TARGET_URL"
  curl -fsS "$TARGET_URL" >/dev/null
  echo "Endpoint responded successfully."
fi
