#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash run_mininet.sh [ovs-user|user]
# Optional:
#   MN_CLEANUP=1 bash run_mininet.sh ovs-user

MODE="${1:-ovs-user}"
CONTROLLER_IP="127.0.0.1"
CONTROLLER_PORT="6633"
WAIT_SECONDS="20"

if [[ "${MN_CLEANUP:-0}" == "1" ]]; then
	echo "[INFO] Optional cleanup enabled (MN_CLEANUP=1)"
	sudo mn -c >/dev/null 2>&1 || true
fi

echo "[INFO] Waiting for controller at ${CONTROLLER_IP}:${CONTROLLER_PORT} (max ${WAIT_SECONDS}s)"
ready="0"
for ((i=1; i<=WAIT_SECONDS; i++)); do
	if (echo > "/dev/tcp/${CONTROLLER_IP}/${CONTROLLER_PORT}") >/dev/null 2>&1; then
		ready="1"
		break
	fi
	sleep 1
done

if [[ "${ready}" != "1" ]]; then
	echo "[ERROR] Controller is not reachable at ${CONTROLLER_IP}:${CONTROLLER_PORT}."
	echo "[ERROR] Start controller first: bash run_controller.sh"
	exit 1
fi

sudo python3 topology.py --switch-mode "${MODE}"
