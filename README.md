wsl SDN Traffic Monitoring and Statistics Collector (Mininet + Ryu)

This project implements an SDN traffic monitoring controller using:
- Mininet topology simulation
- Ryu OpenFlow controller
- OpenFlow 1.3 flow rule installation
- Periodic traffic statistics collection

The implementation is designed for WSL2 and low-resource setups.

## 1. Problem Statement

Goal: demonstrate SDN controller-switch behavior with explicit match-action logic and measurable network behavior.

Required outcomes covered:
- Controller handles PacketIn events
- Explicit flow rules are installed
- Periodic flow statistics are collected
- Normal and high-traffic scenarios are demonstrated
- Validation is shown with ping, iperf, flow tables, and OpenFlow capture

## 2. Project Structure

- traffic_monitor.py: Ryu controller (learning switch + stats + alerts)
- topology.py: Mininet topology runner (single switch, three hosts)
- test_scenario_1.sh: baseline connectivity and throughput script
- test_scenario_2.sh: high-traffic stress script for alert verification
- requirements.txt: Python dependencies for controller
- tools/fix_ryu_eventlet.py: one-time patch for Eventlet API compatibility
- results/: folder for screenshots, logs, and measurements
- DEMO_EXECUTION_GUIDE.md: step-by-step runbook for scenarios + evidence

## 3. Setup (WSL2)

Use Ubuntu 22.04 or newer in WSL2.

### 3.1 Install system dependencies

~~~bash
sudo apt update
sudo apt install -y mininet openvswitch-switch iperf wireshark tshark ethtool python3-pip python3-venv
~~~

### 3.2 Create Python virtual environment

~~~bash
# IMPORTANT: Use Python 3.10 for Ryu compatibility.
# Do not use Conda's Python 3.13 environment for this project.
python3.10 -m venv venv
source venv/bin/activate

# Ryu 4.34 is sensitive to modern build tooling.
pip install --upgrade "pip<25" "setuptools<70" wheel

# Install Ryu with build isolation disabled.
pip install --no-build-isolation ryu==4.34

# Apply compatibility patch for Eventlet API changes.
python tools/fix_ryu_eventlet.py

# Install remaining project dependencies.
pip install -r requirements.txt
~~~

If python3.10 is not available:

~~~bash
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3.10-distutils
~~~

If Ryu installation fails, install additional packages:

~~~bash
sudo apt install -y python3-eventlet python3-greenlet python3-netaddr
~~~

## 4. Run the Project

Important: start controller first, then Mininet.

### 4.1 Terminal A: Start controller

~~~bash
source venv/bin/activate
STATS_INTERVAL=10 ALERT_THRESHOLD_BYTES=1500000 ALERT_THRESHOLD_PACKETS=1500 \
ryu-manager traffic_monitor.py
~~~

Optional blocking scenario (for extra functional demonstration):

~~~bash
source venv/bin/activate
BLOCKED_IP_PAIRS=10.0.0.1-10.0.0.2 ryu-manager traffic_monitor.py
~~~

### 4.2 Terminal B: Start Mininet topology

Preferred (OpenFlow13 + userspace datapath):

~~~bash
sudo python3 topology.py --switch-mode ovs-user
~~~

Project helper script (recommended) waits for controller port `6633` before starting Mininet:

~~~bash
bash run_mininet.sh ovs-user
~~~

Note: helper scripts do not run `mn -c` by default to avoid terminating a running controller. If cleanup is needed, run it manually before starting controller, or use:

~~~bash
MN_CLEANUP=1 bash run_mininet.sh ovs-user
~~~

Direct Mininet equivalent command:

~~~bash
sudo mn --topo single,3 --switch ovs,datapath=user,protocols=OpenFlow13 \
--controller=remote,ip=127.0.0.1,port=6633
~~~

Fallback (legacy userswitch):

~~~bash
sudo python3 topology.py --switch-mode user
~~~

## 5. Test Scenarios

## 5.1 Scenario 1: Normal traffic

### Automated script

~~~bash
bash test_scenario_1.sh ovs-user
~~~

Optional cleanup before the scenario run:

~~~bash
SCENARIO_CLEANUP=1 bash test_scenario_1.sh ovs-user
~~~

### Manual CLI commands

~~~text
mininet> pingall
mininet> h1 ping -c 5 10.0.0.2
mininet> h1 ping -c 5 10.0.0.3
mininet> h2 iperf -s -D
mininet> h1 iperf -c 10.0.0.2 -t 10
~~~

Expected behavior:
- hosts are reachable
- flow rules are installed by the controller
- periodic [STATS] logs appear in controller output

## 5.2 Scenario 2: High traffic

### Automated script

~~~bash
ALERT_THRESHOLD_BYTES=200000 ALERT_THRESHOLD_PACKETS=500 bash test_scenario_2.sh ovs-user
~~~

Optional cleanup before the scenario run:

~~~bash
SCENARIO_CLEANUP=1 bash test_scenario_2.sh ovs-user
~~~

### Manual CLI commands

~~~text
mininet> h1 iperf -s -D
mininet> h2 iperf -c 10.0.0.1 -t 15 -i 1
~~~

Expected behavior:
- packet and byte counters increase quickly
- ALERT lines are printed by controller when threshold is crossed

## 6. Validation and Evidence

Collect proof in results/:
- ping output logs
- iperf output logs
- controller logs with [STATS] and ALERT lines
- flow tables from switch
- OpenFlow packet capture

### 6.1 Flow table inspection

~~~bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
~~~

### 6.2 OpenFlow capture (Wireshark or tshark)

Capture loopback interface and filter by OpenFlow:

~~~text
openflow_v4
~~~

tshark example:

~~~bash
sudo tshark -i lo -f "tcp port 6633" -Y "openflow_v4" -w results/logs/openflow_capture.pcap
~~~

Show evidence of:
- packet_in messages
- flow_mod messages

## 7. Grading Rubric Coverage

1. Problem Understanding and Setup:
- clear objective and setup steps in this README
- Mininet topology and controller configuration documented

2. SDN Logic and Flow Rule Implementation:
- PacketIn handled in traffic_monitor.py
- explicit add_flow logic with priority and timeouts
- OpenFlow1.3 table-miss and learned flows installed

3. Functional Correctness:
- learning-switch forwarding behavior
- monitoring and logging demonstrated
- optional blocked-pair behavior supported via BLOCKED_IP_PAIRS

4. Performance Observation and Analysis:
- latency via ping
- throughput via iperf
- flow counters via flow stats and flow-table dumps


## 8. Troubleshooting

1. Controller not receiving switches:
- confirm controller is started first
- verify port 6633 is listening

2. Hosts cannot reach each other:
- run sudo mn -c
- restart controller and topology
- verify flow entries are created with ovs-ofctl dump-flows
- ensure controller uses permanent table-miss (`idle_timeout=0`) and ARP flood flow (already implemented in `traffic_monitor.py`)
- for OVS userspace datapath reliability, controller forwards packets using explicit `PacketOut` data (does not rely on switch `buffer_id` fast-path)
- for TCP timeouts with successful ping, disable host offloading (already applied in `topology.py` for `ovs-user` mode)

3. Ryu install fails on WSL:
- verify venv uses Python 3.10, not 3.13
- pin tooling: pip<25 and setuptools<70
- install with: pip install --no-build-isolation ryu==4.34
- install python3-eventlet python3-greenlet python3-netaddr if needed

4. ImportError: cannot import name ALREADY_HANDLED from eventlet.wsgi:
- run: python tools/fix_ryu_eventlet.py
- then retry: ryu-manager --version

5. IndentationError after running patch script:
- restore backup: cp venv/lib/python3.10/site-packages/ryu/app/wsgi.py.bak venv/lib/python3.10/site-packages/ryu/app/wsgi.py
- re-run: python tools/fix_ryu_eventlet.py
- retry: ryu-manager --version

6. No ALERT messages:
- lower thresholds in environment variables
- run longer iperf duration or parallel streams


## 9. References

- Mininet: http://mininet.org/
- Ryu documentation: https://ryu.readthedocs.io/
- OpenFlow specification: https://opennetworking.org/
- Wireshark display filters: https://www.wireshark.org/docs/
