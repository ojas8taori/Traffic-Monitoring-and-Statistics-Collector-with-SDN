#!/usr/bin/env bash
set -euo pipefail

# Scenario 1: Normal traffic behavior and baseline measurements.
# Usage:
#   bash test_scenario_1.sh [ovs-user|user]
# Optional:
#   SCENARIO_CLEANUP=1 bash test_scenario_1.sh ovs-user

SWITCH_MODE="${1:-ovs-user}"
RESULT_DIR="results/measurements"
OUT_FILE="${RESULT_DIR}/scenario_1_normal_$(date +%Y%m%d_%H%M%S).log"
CONTROLLER_IP="127.0.0.1"
CONTROLLER_PORT="6633"
WAIT_SECONDS="20"

mkdir -p "${RESULT_DIR}"

if [[ "${SWITCH_MODE}" == "ovs-user" ]]; then
  SWITCH_ARGS="--switch ovs,datapath=user,protocols=OpenFlow13"
else
  SWITCH_ARGS="--switch user"
fi

TMP_CMDS="$(mktemp)"
cat > "${TMP_CMDS}" << 'EOF'
pingall
h1 ping -c 5 10.0.0.2
h1 ping -c 5 10.0.0.3
h2 pkill iperf
h2 iperf -s -p 5001 &
h2 ss -lntp | grep 5001 || echo "iperf server check failed"
h1 iperf -c 10.0.0.2 -p 5001 -t 10 -i 1
h2 pkill iperf
exit
EOF

if [[ "${SCENARIO_CLEANUP:-0}" == "1" ]]; then
  echo "[INFO] Optional cleanup enabled (SCENARIO_CLEANUP=1)"
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
  rm -f "${TMP_CMDS}"
  exit 1
fi

echo "[INFO] Running Scenario 1 in Mininet (${SWITCH_MODE})"
CMD="sudo mn --topo single,3 ${SWITCH_ARGS} --controller=remote,ip=127.0.0.1,port=6633"

echo "[INFO] Command: ${CMD}"
echo "[INFO] Logging output to ${OUT_FILE}"

# shellcheck disable=SC2086
${CMD} < "${TMP_CMDS}" | tee "${OUT_FILE}"

rm -f "${TMP_CMDS}"

echo "[DONE] Scenario 1 complete. Save controller logs and flow tables as evidence."
