#!/usr/bin/env python3
"""
Ryu OpenFlow 1.3 traffic monitor with learning-switch behavior.

Features:
- PacketIn handling with MAC learning
- Explicit match-action flow installation
- Periodic flow statistics collection
- Packet/byte counters and threshold alerts
- Optional IP pair blocking for validation scenarios
"""

import os
from datetime import datetime

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, DEAD_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4
from ryu.lib.packet import packet
from ryu.ofproto import ofproto_v1_3


class TrafficMonitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}

        self.stats_interval = int(os.getenv("STATS_INTERVAL", "10"))
        self.alert_threshold_bytes = int(os.getenv("ALERT_THRESHOLD_BYTES", "1500000"))
        self.alert_threshold_packets = int(os.getenv("ALERT_THRESHOLD_PACKETS", "1500"))
        self.stats_log_file = os.getenv("STATS_LOG_FILE", "/tmp/sdn_flow_stats.log")

        self.blocked_pairs = self._load_blocked_pairs()

        self.monitor_thread = hub.spawn(self._monitor)
        self.logger.info("TrafficMonitor started (OpenFlow 1.3)")
        self.logger.info(
            "Stats interval=%ss, alert bytes=%s, alert packets=%s",
            self.stats_interval,
            self.alert_threshold_bytes,
            self.alert_threshold_packets,
        )
        if self.blocked_pairs:
            self.logger.info("Blocked IPv4 pairs enabled: %s", sorted(self.blocked_pairs))

    def _load_blocked_pairs(self):
        """
        Format: BLOCKED_IP_PAIRS=10.0.0.1-10.0.0.2,10.0.0.3-10.0.0.2
        """
        value = os.getenv("BLOCKED_IP_PAIRS", "").strip()
        blocked = set()
        if not value:
            return blocked

        for item in value.split(","):
            token = item.strip()
            if not token or "-" not in token:
                continue
            a, b = token.split("-", 1)
            a = a.strip()
            b = b.strip()
            if a and b:
                blocked.add((a, b))
                blocked.add((b, a))

        return blocked

    def _is_blocked_ip_pair(self, src_ip, dst_ip):
        return (src_ip, dst_ip) in self.blocked_pairs

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        dpid = format(datapath.id, "016x")

        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.datapaths[datapath.id] = datapath
                self.logger.info("Switch connected: dpid=%s", dpid)
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                del self.datapaths[datapath.id]
                self.logger.info("Switch disconnected: dpid=%s", dpid)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Keep ARP working even if learned flows age out.
        arp_match = parser.OFPMatch(eth_type=0x0806)
        arp_actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.add_flow(
            datapath,
            priority=100,
            match=arp_match,
            actions=arp_actions,
            idle_timeout=0,
            hard_timeout=0,
        )

        # Table-miss rule: send unmatched packets to controller.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(
            datapath,
            priority=0,
            match=match,
            actions=actions,
            idle_timeout=0,
            hard_timeout=0,
        )

        self.logger.info("Installed ARP and table-miss flows on dpid=%016x", datapath.id)

    def add_flow(
        self,
        datapath,
        priority,
        match,
        actions,
        idle_timeout=0,
        hard_timeout=0,
        buffer_id=None,
    ):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        if buffer_id is not None and buffer_id != ofproto.OFP_NO_BUFFER:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                buffer_id=buffer_id,
                priority=priority,
                match=match,
                idle_timeout=idle_timeout,
                hard_timeout=hard_timeout,
                instructions=instructions,
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                idle_timeout=idle_timeout,
                hard_timeout=hard_timeout,
                instructions=instructions,
            )

        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None:
            return

        # Ignore LLDP frames to avoid unnecessary controller processing.
        if eth.ethertype == 0x88CC:
            return

        dpid = format(datapath.id, "016x")
        self.mac_to_port.setdefault(dpid, {})

        src = eth.src
        dst = eth.dst

        self.mac_to_port[dpid][src] = in_port

        ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
        if ipv4_pkt and self._is_blocked_ip_pair(ipv4_pkt.src, ipv4_pkt.dst):
            drop_match = parser.OFPMatch(
                eth_type=0x0800,
                ipv4_src=ipv4_pkt.src,
                ipv4_dst=ipv4_pkt.dst,
            )
            self.add_flow(
                datapath,
                priority=200,
                match=drop_match,
                actions=[],
                idle_timeout=120,
                hard_timeout=0,
            )
            self.logger.warning("Blocked flow installed: %s -> %s", ipv4_pkt.src, ipv4_pkt.dst)
            return

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            self.add_flow(
                datapath,
                priority=1,
                match=match,
                actions=actions,
                idle_timeout=120,
                hard_timeout=0,
            )

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port,
            actions=actions,
            data=msg.data,
        )
        datapath.send_msg(out)

    def _monitor(self):
        while True:
            for datapath in list(self.datapaths.values()):
                self._request_stats(datapath)
            hub.sleep(self.stats_interval)

    def _request_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        dpid = format(ev.msg.datapath.id, "016x")

        # Filter out only non-table-miss entries for cleaner reporting.
        flow_stats = [f for f in body if f.priority > 0]
        if not flow_stats:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        total_packets = 0
        total_bytes = 0
        lines = []

        for stat in sorted(flow_stats, key=lambda x: (x.priority, x.packet_count, x.byte_count)):
            total_packets += stat.packet_count
            total_bytes += stat.byte_count

            match_text = ", ".join([f"{k}={v}" for k, v in stat.match.items()])
            if not match_text:
                match_text = "any"

            line = (
                f"priority={stat.priority} | packets={stat.packet_count} | bytes={stat.byte_count} | "
                f"duration={stat.duration_sec}s | match={match_text}"
            )
            lines.append(line)

            if (
                stat.byte_count >= self.alert_threshold_bytes
                or stat.packet_count >= self.alert_threshold_packets
            ):
                self.logger.warning(
                    "ALERT high traffic on dpid=%s: packets=%s bytes=%s match=%s",
                    dpid,
                    stat.packet_count,
                    stat.byte_count,
                    match_text,
                )

        header = f"[STATS] {timestamp} | dpid={dpid}"
        summary = f"TOTAL packets={total_packets} bytes={total_bytes}"

        self.logger.info(header)
        for line in lines:
            self.logger.info("  %s", line)
        self.logger.info(summary)

        self._append_stats_to_file(header, lines, summary)

    def _append_stats_to_file(self, header, lines, summary):
        try:
            with open(self.stats_log_file, "a", encoding="utf-8") as f:
                f.write(header + "\n")
                for line in lines:
                    f.write("  " + line + "\n")
                f.write(summary + "\n")
                f.write("-" * 80 + "\n")
        except OSError as exc:
            self.logger.error("Failed to write stats log: %s", exc)
