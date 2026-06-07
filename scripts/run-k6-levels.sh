#!/usr/bin/env bash
set -euo pipefail

# Runs the progressive load levels defined for the experiment.
# Main variables:
#   TARGET_URL=http://127.0.0.1:8080/
#   SCENARIO=C1|C2|C3|C4
#   EXPERIMENT_PHASE=exploratory|confirmatory
#   EXPLORATORY_REPLICATIONS=1
#   REPLICATIONS=30
#   RAMP_UP=5s
#   WARMUP=5s
#   DURATION=15s
#   COOLDOWN=0
#   EXPORT_RAW=true

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K6_SCRIPT="$ROOT_DIR/k6/scripts/load-test.js"
LEVELS_FILE="${LEVELS_FILE:-$ROOT_DIR/k6/scenarios/load-levels.json}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT_DIR/results}"
RAW_RESULTS_DIR="${RAW_RESULTS_DIR:-$RESULTS_DIR/raw}"
LOGS_DIR="${LOGS_DIR:-$RESULTS_DIR/logs}"
TARGET_URL="${TARGET_URL:-http://127.0.0.1:8080/}"
SCENARIO="${SCENARIO:-manual}"
EXPERIMENT_PHASE="${EXPERIMENT_PHASE:-exploratory}"
EXPLORATORY_REPLICATIONS="${EXPLORATORY_REPLICATIONS:-1}"
RAMP_UP="${RAMP_UP:-}"
WARMUP="${WARMUP:-}"
DURATION_OVERRIDE="${DURATION:-}"
COOLDOWN="${COOLDOWN:-}"
EXPORT_RAW="${EXPORT_RAW:-true}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_NAME="${SCENARIO}_${EXPERIMENT_PHASE}_${RUN_ID}"
RUN_DIR="$RAW_RESULTS_DIR/$RUN_NAME"
RUN_LOG_DIR="$LOGS_DIR/$RUN_NAME"

case "$EXPERIMENT_PHASE" in
  exploratory)
    REPLICATIONS="${REPLICATIONS:-$EXPLORATORY_REPLICATIONS}"
    RAMP_UP="${RAMP_UP:-5s}"
    WARMUP="${WARMUP:-5s}"
    DURATION_OVERRIDE="${DURATION_OVERRIDE:-15s}"
    COOLDOWN="${COOLDOWN:-0}"
    ;;
  confirmatory)
    REPLICATIONS="${REPLICATIONS:-30}"
    RAMP_UP="${RAMP_UP:-1m}"
    WARMUP="${WARMUP:-1m}"
    COOLDOWN="${COOLDOWN:-30}"
    ;;
  *)
    echo "Error: EXPERIMENT_PHASE must be 'exploratory' or 'confirmatory'."
    exit 1
    ;;
esac

if ! command -v k6 >/dev/null 2>&1; then
  echo "Error: k6 was not found in PATH."
  echo "Install k6 on the load client before running the tests."
  exit 1
fi

mkdir -p "$RUN_DIR" "$RUN_LOG_DIR"

if command -v jq >/dev/null 2>&1; then
  mapfile -t LEVELS < <(jq -r '.levels[] | "\(.level),\(.vus),\(.duration)"' "$LEVELS_FILE")
else
  echo "Warning: jq was not found. Using default levels embedded in the script."
  LEVELS=(
    "1,50,5m"
    "2,75,5m"
    "3,112,5m"
    "4,168,5m"
    "5,252,5m"
    "6,378,5m"
  )
fi

cat > "$RUN_DIR/metadata.env" <<EOF
RUN_ID=$RUN_ID
RUN_NAME=$RUN_NAME
SCENARIO=$SCENARIO
EXPERIMENT_PHASE=$EXPERIMENT_PHASE
TARGET_URL=$TARGET_URL
LEVELS_FILE=$LEVELS_FILE
COOLDOWN=$COOLDOWN
REPLICATIONS=$REPLICATIONS
EXPLORATORY_REPLICATIONS=$EXPLORATORY_REPLICATIONS
RAMP_UP=$RAMP_UP
WARMUP=$WARMUP
DURATION_OVERRIDE=$DURATION_OVERRIDE
EXPORT_RAW=$EXPORT_RAW
EOF

cp "$RUN_DIR/metadata.env" "$RUN_LOG_DIR/metadata.env"

for level_spec in "${LEVELS[@]}"; do
  IFS=',' read -r LEVEL VUS DURATION <<< "$level_spec"

  if [[ -n "$DURATION_OVERRIDE" ]]; then
    DURATION="$DURATION_OVERRIDE"
  fi

  for replication in $(seq 1 "$REPLICATIONS"); do
    SUMMARY_FILE="$RUN_DIR/level-${LEVEL}-vus-${VUS}-rep-${replication}-summary.json"
    RAW_FILE="$RUN_DIR/level-${LEVEL}-vus-${VUS}-rep-${replication}-raw.jsonl"
    LOG_FILE="$RUN_LOG_DIR/level-${LEVEL}-vus-${VUS}-rep-${replication}.log"

    echo "Running phase $EXPERIMENT_PHASE, level $LEVEL, replication $replication/$REPLICATIONS: VUS=$VUS, RAMP_UP=$RAMP_UP, WARMUP=$WARMUP, DURATION=$DURATION, TARGET_URL=$TARGET_URL"

    if [[ "$EXPORT_RAW" == "true" ]]; then
      TARGET_URL="$TARGET_URL" VUS="$VUS" RAMP_UP="$RAMP_UP" WARMUP="$WARMUP" DURATION="$DURATION" SCENARIO="$SCENARIO" \
        k6 run --summary-export "$SUMMARY_FILE" --out "json=$RAW_FILE" "$K6_SCRIPT" 2>&1 | tee "$LOG_FILE"
    else
      TARGET_URL="$TARGET_URL" VUS="$VUS" RAMP_UP="$RAMP_UP" WARMUP="$WARMUP" DURATION="$DURATION" SCENARIO="$SCENARIO" \
        k6 run --summary-export "$SUMMARY_FILE" "$K6_SCRIPT" 2>&1 | tee "$LOG_FILE"
    fi

    echo "Summary saved to $SUMMARY_FILE"
    echo "Log saved to $LOG_FILE"

    if [[ "$COOLDOWN" != "0" ]]; then
      echo "Waiting for a cooldown of $COOLDOWN seconds."
      sleep "$COOLDOWN"
    fi
  done
done

echo "Run completed. Results in $RUN_DIR"
echo "Logs in $RUN_LOG_DIR"
