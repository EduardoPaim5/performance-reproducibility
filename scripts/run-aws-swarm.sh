#!/usr/bin/env bash
set -euo pipefail

# C4: helper to publish the stack to an already prepared AWS EC2 instance.
# The script does not create credentials, security groups, instances, or network rules.
# Use placeholders through environment variables before enabling DEPLOY_AWS=true.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AWS_SSH_HOST="${AWS_SSH_HOST:-}"
AWS_SSH_USER="${AWS_SSH_USER:-ec2-user}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-~/performance-reproducibility}"
STACK_NAME="${STACK_NAME:-perf-aws}"
DEPLOY_AWS="${DEPLOY_AWS:-false}"
NGINX_PUBLISHED_PORT="${NGINX_PUBLISHED_PORT:-80}"

if [[ -z "$AWS_SSH_HOST" ]]; then
  echo "Set AWS_SSH_HOST to the public IP or DNS name of the EC2 instance."
  echo "Example: AWS_SSH_HOST=ec2-203-0-113-10.compute-1.amazonaws.com"
  exit 1
fi

if [[ "$DEPLOY_AWS" != "true" ]]; then
  echo "No remote action was run."
  echo "Review the EC2 instance, Docker Swarm, security groups, and monitoring/prometheus/prometheus.yml."
  echo "To publish through SSH, run again with DEPLOY_AWS=true."
  exit 0
fi

if ! command -v ssh >/dev/null 2>&1; then
  echo "Error: ssh was not found in PATH."
  exit 1
fi

if ! command -v tar >/dev/null 2>&1; then
  echo "Error: tar was not found in PATH."
  exit 1
fi

echo "Copying minimum files to $AWS_SSH_USER@$AWS_SSH_HOST:$REMOTE_APP_DIR"
ssh "$AWS_SSH_USER@$AWS_SSH_HOST" "mkdir -p $REMOTE_APP_DIR"
tar -C "$ROOT_DIR" -cz nginx docker/swarm | ssh "$AWS_SSH_USER@$AWS_SSH_HOST" "tar -xz -C $REMOTE_APP_DIR"

echo "Publishing stack $STACK_NAME to the remote instance."
ssh "$AWS_SSH_USER@$AWS_SSH_HOST" "cd $REMOTE_APP_DIR/docker/swarm && NGINX_PUBLISHED_PORT=$NGINX_PUBLISHED_PORT docker stack deploy -c stack.yml $STACK_NAME"

echo "C4 published. Expected target URL: http://$AWS_SSH_HOST:$NGINX_PUBLISHED_PORT/"
