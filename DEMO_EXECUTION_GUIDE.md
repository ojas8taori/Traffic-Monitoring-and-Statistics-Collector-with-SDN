# SDN Demo Execution Guide (Step by Step)

This guide is the exact runbook for demonstrating all required functionality in the Mininet + Ryu traffic monitoring project on WSL2.

It covers:
- Full startup flow
- Functional behavior proof
- 2 required test scenarios (Allowed and Blocked)
- Basic regression validation
- iperf, flow-table, and OpenFlow capture evidence
- Screenshot points and naming

## 1. Evidence Folder Setup

Run once from project root:

```bash
mkdir -p results/screenshots results/logs results/measurements
```

Use this naming convention for screenshots:
- `results/screenshots/SS01_controller_started.png`
- `results/screenshots/SS02_switch_connected.png`
- `results/screenshots/SS03_pingall_normal.png`
- `results/screenshots/SS04_iperf_normal.png`
- `results/screenshots/SS05_flow_table_normal.png`
- `results/screenshots/SS06_openflow_capture.png`
- `results/screenshots/SS07_blocked_ping_fail.png`
- `results/screenshots/SS08_unblocked_regression_pass.png`

## 2. Pre-Run Cleanup (One Time per Fresh Run)

In a new WSL terminal:

```bash
cd /mnt/c/OJ/sem4/CN/orange-2.1
sudo mn -c
```

## 3. Terminal Layout

Use 3 terminals:
- Terminal A: Ryu controller
- Terminal B: Mininet CLI
- Terminal C: Validation commands (flow dump, packet capture, logs)

## 4. Start Controller (Terminal A)

```bash
cd /mnt/c/OJ/sem4/CN/orange-2.1
source venv/bin/activate
bash run_controller.sh
```

Expected indicators:
- `TrafficMonitor started (OpenFlow 1.3)`
- `Stats interval=10s...`
- After Mininet starts: `Switch connected: dpid=...`

Take screenshot:
- `SS01_controller_started.png` after startup lines appear.
- `SS02_switch_connected.png` once switch connection appears.

## 5. Start Topology (Terminal B)

```bash
cd /mnt/c/OJ/sem4/CN/orange-2.1
bash run_mininet.sh ovs-user
```

Expected:
- Mininet CLI prompt appears: `mininet>`

## 6. Scenario 1: Allowed / Normal Traffic

Goal:
- Prove forwarding works
- Prove monitoring/stats updates
- Measure latency and throughput

Run in Mininet (Terminal B):

```bash
pingall
h1 ping -c 5 10.0.0.2
h2 pkill iperf
h2 iperf -s -p 5001 &
h1 iperf -c 10.0.0.2 -p 5001 -t 10 -i 1
```

Expected:
- `pingall`: 0% drop
- `h1 ping`: 0% loss with low ms RTT
- `iperf`: successful connection and bandwidth lines

Take screenshots:
- `SS03_pingall_normal.png` (pingall success)
- `SS04_iperf_normal.png` (iperf summary)

Controller evidence (Terminal A):
- `[STATS]` blocks every 10 seconds
- packet/byte totals increase over time

Save key controller output:

```bash
# Terminal C
cp /tmp/sdn_flow_stats.log results/logs/controller_stats_normal.log
```

## 7. Flow Rule Validation (OpenFlow Table)

Run from Terminal C while Mininet is still running:

```bash
cd /mnt/c/OJ/sem4/CN/orange-2.1
sudo ovs-ofctl -O OpenFlow13 dump-flows s1 | tee results/logs/flows_normal.txt
```

Expected entries include:
- ARP flood rule (priority 100)
- Table-miss rule (priority 0 -> CONTROLLER)
- Learned forwarding rule(s) (priority 1)

Take screenshot:
- `SS05_flow_table_normal.png`

## 8. OpenFlow Packet Validation (Wireshark/tshark)

Start capture in Terminal C:

Note: when saving with `-w`, tshark cannot apply a display filter (`-Y`) during capture. Use a capture filter (`-f`) while recording, then apply `-Y` when reading the file (or in Wireshark).

```bash
cd /mnt/c/OJ/sem4/CN/orange-2.1
sudo tshark -i lo -f "tcp port 6633" -w results/logs/openflow_capture.pcap
```

While capture runs, generate traffic in Mininet:

```bash
h1 ping -c 3 10.0.0.2
```

Stop tshark with Ctrl+C.

Expected in capture:
- `packet_in`
- `flow_mod`

Optional display filter if opening in Wireshark:
- `openflow_v4`

Validate quickly in terminal (post-capture):

```bash
tshark -r results/logs/openflow_capture.pcap -Y "openflow_v4" | head
```

Take screenshot:
- `SS06_openflow_capture.png` (showing OpenFlow messages)

## 9. Scenario 2: Blocked Traffic (Allowed vs Blocked)

Goal:
- Demonstrate policy behavior change using explicit blocking logic

### 9.1 Stop current run

- In Mininet: `exit`
- In controller terminal: `Ctrl+C`

### 9.2 Restart controller with block policy (Terminal A)

```bash
cd /mnt/c/OJ/sem4/CN/orange-2.1
source venv/bin/activate
BLOCKED_IP_PAIRS=10.0.0.1-10.0.0.2 bash run_controller.sh
```

### 9.3 Restart Mininet (Terminal B)

```bash
cd /mnt/c/OJ/sem4/CN/orange-2.1
bash run_mininet.sh ovs-user
```

### 9.4 Run blocked tests (Terminal B)

```bash
h1 ping -c 5 10.0.0.2
h1 ping -c 5 10.0.0.3
```

Expected:
- `h1 -> h2` fails or high loss (blocked)
- `h1 -> h3` succeeds (not blocked)

Take screenshot:
- `SS07_blocked_ping_fail.png`

Controller evidence (Terminal A):
- `Blocked flow installed: 10.0.0.1 -> 10.0.0.2`

Save logs:

```bash
# Terminal C
cp /tmp/sdn_flow_stats.log results/logs/controller_stats_blocked.log
```

## 10. Regression Check (Unblock and Re-test)

Goal:
- Show behavior recovers when block policy is removed

### 10.1 Stop blocked run

- In Mininet: `exit`
- In controller terminal: `Ctrl+C`

### 10.2 Restart in normal mode

Terminal A:

```bash
cd /mnt/c/OJ/sem4/CN/orange-2.1
source venv/bin/activate
bash run_controller.sh
```

Terminal B:

```bash
cd /mnt/c/OJ/sem4/CN/orange-2.1
bash run_mininet.sh ovs-user
```

### 10.3 Re-test connectivity

```bash
h1 ping -c 5 10.0.0.2
```

Expected:
- Ping succeeds again (regression passed)

Take screenshot:
- `SS08_unblocked_regression_pass.png`

## 11. Quick Viva Checklist

Use these points during explanation:
- Controller-switch interaction: shown by switch connect log and OpenFlow capture
- Match-action logic: visible in learned flows (`in_port`, `eth_src`, `eth_dst`, output action)
- PacketIn handling: table-miss to controller and dynamic flow installs
- Monitoring: periodic `[STATS]` counters (packet/byte)
- Scenario-based behavior: Allowed vs Blocked verified
- Validation tools: ping, iperf, ovs-ofctl, tshark/Wireshark

## 12. Final Submission Checklist

Before push:
- Code files present and clean
- Public GitHub repo ready
- README includes expected and actual results
- Evidence files saved in `results/`
- Screenshots attached and named clearly
- Flow table, ping, iperf, and OpenFlow proof included
