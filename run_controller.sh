#!/usr/bin/env bash
set -euo pipefail

# Usage examples:
#   bash run_controller.sh
#   ALERT_THRESHOLD_BYTES=200000 ALERT_THRESHOLD_PACKETS=500 bash run_controller.sh
#   BLOCKED_IP_PAIRS=10.0.0.1-10.0.0.2 bash run_controller.sh

source venv/bin/activate

: "${STATS_INTERVAL:=10}"
: "${ALERT_THRESHOLD_BYTES:=1500000}"
: "${ALERT_THRESHOLD_PACKETS:=1500}"

export STATS_INTERVAL
export ALERT_THRESHOLD_BYTES
export ALERT_THRESHOLD_PACKETS

# Keep Ryu compatible with newer Eventlet versions.
if [[ -f tools/fix_ryu_eventlet.py ]]; then
	python tools/fix_ryu_eventlet.py || true
fi

exec ryu-manager traffic_monitor.py
