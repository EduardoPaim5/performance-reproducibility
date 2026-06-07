#!/usr/bin/env bash
set -euo pipefail

# C3: publishes Nginx in local Docker Swarm.
# If Swarm is not active yet, set INIT_SWARM=true to initialize it.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK_DIR="$ROOT_DIR/docker/swarm"
STACK_NAME="${STACK_NAME:-perf-local}"
INIT_SWARM="${INIT_SWARM:-false}"
NGINX_PUBLISHED_PORT="${NGINX_PUBLISHED_PORT:-8080}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker was not found in PATH."
  exit 1
fi

SWARM_STATE="$(docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null || echo inactive)"

if [[ "$SWARM_STATE" != "active" ]]; then
  if [[ "$INIT_SWARM" == "true" ]]; then
    docker swarm init
  else
    echo "Docker Swarm is not active."
    echo "Run again with INIT_SWARM=true if you want to initialize Swarm on this host."
    exit 1
  fi
fi

cd "$STACK_DIR"
NGINX_PUBLISHED_PORT="$NGINX_PUBLISHED_PORT" docker stack deploy -c stack.yml "$STACK_NAME"

echo "C3 published to local Swarm."
echo "Stack: $STACK_NAME"
echo "Target URL: http://127.0.0.1:$NGINX_PUBLISHED_PORT/"
echo "Check services: docker stack services $STACK_NAME"
