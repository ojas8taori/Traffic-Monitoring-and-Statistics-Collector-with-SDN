#!/usr/bin/env python3
"""
WSL-friendly Mininet topology for Ryu traffic monitoring project.

Default switch mode is OVS userspace datapath (OpenFlow 1.3 capable).
Use --switch-mode user only if your environment cannot run OVS userspace.
"""

import argparse

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController, UserSwitch


def disable_host_offload(net):
    """
    OVS userspace datapath in WSL can exhibit checksum/offload quirks.
    Disabling offload keeps TCP behavior stable for iperf tests.
    """
    for host_name in ["h1", "h2", "h3"]:
        host = net.get(host_name)
        iface = f"{host_name}-eth0"
        host.cmd(f"ethtool -K {iface} rx off tx off sg off tso off ufo off gso off gro off lro off")
        info(f"*** Offload disabled on {iface}\n")


def build_network(switch_mode):
    net = Mininet(controller=None, link=TCLink, autoSetMacs=True, build=False)

    info("*** Adding remote controller c0 (127.0.0.1:6633)\n")
    net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6633)

    info("*** Adding hosts\n")
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")

    info("*** Adding switch\n")
    if switch_mode == "ovs-user":
        s1 = net.addSwitch("s1", cls=OVSSwitch, protocols="OpenFlow13", datapath="user")
        info("*** Switch mode: OVS userspace datapath (OpenFlow13)\n")
    else:
        s1 = net.addSwitch("s1", cls=UserSwitch)
        info("*** Switch mode: UserSwitch (legacy; OpenFlow13 may not be available)\n")

    info("*** Creating links\n")
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s1)

    return net


def run_topology(switch_mode):
    net = build_network(switch_mode)

    info("*** Building network\n")
    net.build()

    info("*** Starting network\n")
    net.start()

    if switch_mode == "ovs-user":
        disable_host_offload(net)

    info("*** Nodes\n")
    info(net.__repr__() + "\n")

    info("*** Suggested quick checks:\n")
    info("    pingall\n")
    info("    h1 ping -c 5 10.0.0.2\n")
    info("    h1 ping -c 5 10.0.0.3\n")

    CLI(net)

    info("*** Stopping network\n")
    net.stop()


def parse_args():
    parser = argparse.ArgumentParser(description="Run Mininet topology for SDN traffic monitor")
    parser.add_argument(
        "--switch-mode",
        choices=["ovs-user", "user"],
        default="ovs-user",
        help="Switch type to use (default: ovs-user)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    setLogLevel("info")
    args = parse_args()
    run_topology(args.switch_mode)
