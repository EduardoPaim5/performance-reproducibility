#!/usr/bin/env bash
set -euo pipefail

# C1: runs native Nginx using an isolated repository configuration.
# This script does not change system services. It creates temporary files
# in results/native-nginx and starts a separate nginx process.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8080}"
RUN_DIR="$ROOT_DIR/results/native-nginx"
PID_FILE="$RUN_DIR/nginx.pid"
CONF_FILE="$RUN_DIR/nginx-native.conf"

if ! command -v nginx >/dev/null 2>&1; then
  echo "Error: nginx was not found in PATH. Install native Nginx before running C1."
  exit 1
fi

mkdir -p "$RUN_DIR/logs" \
  "$RUN_DIR/client_body_temp" \
  "$RUN_DIR/proxy_temp" \
  "$RUN_DIR/fastcgi_temp" \
  "$RUN_DIR/uwsgi_temp" \
  "$RUN_DIR/scgi_temp"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Native Nginx is already running with PID $(cat "$PID_FILE")."
  echo "Target URL: http://127.0.0.1:$PORT/"
  exit 0
fi

cat > "$CONF_FILE" <<EOF
worker_processes auto;
pid $PID_FILE;

events {
  worker_connections 1024;
}

http {
  include /etc/nginx/mime.types;
  default_type application/octet-stream;

  access_log $RUN_DIR/logs/access.log;
  error_log $RUN_DIR/logs/error.log warn;

  sendfile on;
  tcp_nopush on;
  keepalive_timeout 65;

  server {
    listen $PORT;
    server_name localhost;

    root $ROOT_DIR/nginx/html;
    index index.html;

    location / {
      try_files \$uri \$uri/ =404;
    }

    location = /health {
      access_log off;
      return 200 "ok\n";
      add_header Content-Type text/plain;
    }
  }
}
EOF

nginx -p "$RUN_DIR/" -c "$CONF_FILE"

echo "C1 started: native Nginx at http://127.0.0.1:$PORT/"
echo "To stop: nginx -p \"$RUN_DIR/\" -c \"$CONF_FILE\" -s stop"
