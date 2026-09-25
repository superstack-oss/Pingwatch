from __future__ import annotations

from typing import Any, Dict, List, Optional

ERROR_LABELS = {
    "ok": "Reachable",
    "dns": "DNS resolution failed",
    "network": "Network unreachable",
    "no_route": "No route to host",
    "host_unreachable": "Host unreachable",
    "ttl": "TTL exceeded",
    "filtered": "ICMP administratively filtered",
    "timeout": "Request timeout",
    "icmp_filtered": "ICMP filtered, TCP still answers",
    "latency": "Elevated latency",
    "tcp": "TCP handshake failed",
    "websocket": "WebSocket handshake failed",
    "grpc": "gRPC health is not SERVING",
    "game": "Game server query failed",
    "unknown": "Host unreachable",
}

KIND_PORTS = {
    "nas": (22, 80, 443, 445, 139, 111, 2049, 548),
    "storage": (22, 80, 443, 5988, 5989, 8080),
    "san": (22, 23, 80, 443),
    "network": (22, 23, 80, 443),
    "server": (22, 80, 443, 3389, 445),
    "other": (22, 80, 443),
}

KIND_CHECKS = {
    "nas": [
        "Confirm the ping target is the NAS management or cluster IP, not a client data share path.",
        "Check whether SMB/NFS still works from a client — some NAS units drop ICMP while file services stay up.",
        "Review NIC teaming, the management VLAN, and the default gateway on the NAS.",
        "Look at the NAS event log for NIC, HA failover, or controller reboot messages.",
    ],
    "storage": [
        "Ping the array management IP (SP/controller or cluster-mgmt), not a front-end data port that may ignore ICMP.",
        "Check both storage processors / controllers. One SP reboot can take a management address offline.",
        "Verify the management VLAN, default gateway, and that a jump host on the same VLAN can open Unisphere, SSMC, or ONTAP System Manager.",
        "Ask storage/SAN whether a fabric, IP management, or site outage is also affecting peer arrays (EMC, HPE, NetApp, and similar).",
        "If only ICMP fails, try HTTPS to the array UI before declaring a full array outage.",
    ],
    "san": [
        "Many Brocade, Cisco MDS, and similar SAN switches disable ICMP on the management interface. Try SSH or HTTPS before assuming the switch is down.",
        "Confirm you are targeting the management IP, not a data-plane FC address.",
        "Check the management VRF/VLAN, default gateway, and that a fabric jump host can still SSH.",
        "Look for supervisor failover, dual-CP reboot, or management port flap in the switch logs.",
        "See whether neighbouring switches in the same fabric are also unreachable — that points to a management network issue, not a single director.",
    ],
    "network": [
        "Cisco, Aruba, and other network OS images often rate-limit or disable ICMP. Test SSH/HTTPS and SNMP from the same subnet.",
        "Confirm the address is the management SVI or dedicated mgmt port, not a user VLAN that filters ping.",
        "Check uplinks, the default gateway, and any ACL or control-plane policy that could drop ICMP from the Pingwatch host.",
        "If the whole access layer is dark, inspect the upstream core/distribution path rather than a single edge switch.",
    ],
    "server": [
        "Check whether the OS is running: console/iLO/iDRAC/IPMI, hypervisor vMotion state, and guest tools.",
        "Verify the NIC, bond/team, and that the monitoring host is allowed through host firewalls.",
        "A timeout with no ICMP unreachable often means a hung OS, NIC reset, or the packet is being dropped silently.",
        "If this is a VM, check the hypervisor host and virtual switch/port group as well as the guest.",
    ],
    "other": [
        "Confirm the IP/hostname still belongs to this endpoint and that ICMP is allowed from the Pingwatch host.",
        "Try a second path: SSH, HTTPS, or a vendor UI from a jump host on the same network.",
        "Check local routing, VLAN, and firewall policy on the monitoring server.",
        "If several endpoints in the same subnet fail together, investigate the shared switch, gateway, or uplink first.",
    ],
}


def error_code(message: Optional[str]) -> str:
    text = (message or "").lower()
    if not text:
        return "unknown"
    if "dns" in text or "unknown host" in text or "not known" in text:
        return "dns"
    if "administratively" in text or "prohibited" in text or "filtered" in text:
        return "filtered"
    if "ttl" in text or "time to live" in text:
        return "ttl"
    if "no route" in text:
        return "no_route"
    if "network is unreachable" in text or "network unreachable" in text:
        return "network"
    if "destination host unreachable" in text or "host unreachable" in text:
        return "host_unreachable"
    if "timeout" in text or "timed out" in text or "packet loss" in text:
        return "timeout"
    if "icmp filtered" in text:
        return "icmp_filtered"
    if "tcp handshake" in text:
        return "tcp"
    if "websocket" in text:
        return "websocket"
    if "grpc" in text or "serving" in text:
        return "grpc"
    if "game server" in text or "a2s" in text or "gamespy" in text:
        return "game"
    if "nxdomain" in text or "no aaaa" in text or "no a records" in text:
        return "dns"
    return "unknown"


def classify_from_output(output: str, returncode: Optional[int]) -> str:
    text = (output or "").lower()
    if "unknown host" in text or "name or service not known" in text or "not known" in text or "temporary failure in name resolution" in text:
        return ERROR_LABELS["dns"]
    if "network is unreachable" in text:
        return ERROR_LABELS["network"]
    if "no route to host" in text:
        return ERROR_LABELS["no_route"]
    if "time to live" in text or "ttl expired" in text or ("ttl" in text and "exceeded" in text):
        return ERROR_LABELS["ttl"]
    if "administratively prohibited" in text or "communication administratively" in text:
        return ERROR_LABELS["filtered"]
    if "destination host unreachable" in text or "host unreachable" in text:
        return ERROR_LABELS["host_unreachable"]
    if "destination net unreachable" in text or "net unreachable" in text:
        return ERROR_LABELS["no_route"]
    if "100% packet loss" in text or "100.0% packet loss" in text or "timed out" in text or "timeout" in text:
        return ERROR_LABELS["timeout"]
    if returncode not in (0, None):
        return ERROR_LABELS["unknown"]
    return ERROR_LABELS["unknown"]


def last_responding_hop(hops: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not hops:
        return None
    last = None
    for hop in hops:
        if hop.get("host"):
            last = hop
    if last is None:
        return "No hop responded. The path is failing at or immediately after the Pingwatch host."
    last_no = int(last.get("hop") or 0)
    max_no = max(int(item.get("hop") or 0) for item in hops)
    host = last.get("host")
    if last_no < max_no:
        return "Path is alive through hop %s (%s). Failure is beyond that hop, toward the target." % (last_no, host)
    return "Traceroute reached hop %s (%s)." % (last_no, host)


def _monitor_insight(
    probe: str,
    kind_key: str,
    host: str,
    error: Optional[str],
    failure_count: int,
) -> Dict[str, Any]:
    code = error_code(error)
    if probe == "tcp":
        code = "tcp" if code in {"timeout", "unknown", "filtered"} else code
        where = "A TCP handshake to %s did not complete." % host
        likely = "The listener is down, firewalled, or bound to a different address than the monitor target."
        checks = [
            "Confirm the host and port still belong to this service.",
            "From a jump host, try `nc -vz` or an equivalent TCP connect to the same port.",
            "Check the process, container, and host firewall on the target.",
        ]
    elif probe == "dns":
        code = "dns"
        where = "The DNS lookup against the chosen resolver did not return a record for %s." % host
        likely = "The zone expired, the record was removed, or the resolver is failing."
        checks = [
            "Query the same name and type with dig against the configured resolver.",
            "Confirm the zone is still delegated and the record has not expired.",
            "Try a second resolver to separate a dead resolver from a missing record.",
        ]
    elif probe == "websocket":
        code = "websocket"
        where = "The WebSocket upgrade to %s did not complete." % host
        likely = "The endpoint is down, TLS is misconfigured, or a proxy is no longer forwarding the Upgrade header."
        checks = [
            "Open the ws:// or wss:// URL from a client on the same network.",
            "Confirm the path, port, and TLS certificate still match the monitor.",
            "Check reverse-proxy Upgrade/Connection headers if a load balancer sits in front.",
        ]
    elif probe == "grpc":
        code = "grpc"
        where = "The gRPC health service on %s did not report SERVING." % host
        likely = "The process is down, the health service is disabled, or the named service is not SERVING."
        checks = [
            "Call grpc.health.v1.Health/Check against the same host and port.",
            "If you named a service, confirm that service is registered and SERVING.",
            "Inspect process logs for failed dependencies that keep the health status from SERVING.",
        ]
    else:
        code = "game"
        where = "The native game-server query to %s did not get a valid reply." % host
        likely = "The game process crashed, the query port changed, or a host firewall is dropping the protocol."
        checks = [
            "Confirm the game type and query port still match the running server.",
            "Check the game process and its query/listen ports on the host.",
            "If only the query port is dark, players may already be unable to join.",
        ]
    title = ERROR_LABELS.get(code, "Unreachable")
    summary = error or title
    if failure_count > 1:
        summary = "%s Repeated %s times in this outage." % (summary.rstrip("."), failure_count)
    return {
        "code": code,
        "title": title,
        "summary": summary,
        "where": where,
        "likely_cause": likely,
        "checks": (checks + KIND_CHECKS[kind_key][:2])[:6],
    }


def build_insight(
    kind: Optional[str],
    host: str,
    *,
    status: str = "down",
    error: Optional[str] = None,
    rtt_ms: Optional[float] = None,
    warning_rtt_ms: float = 200.0,
    tcp_open: Optional[List[int]] = None,
    traceroute_hops: Optional[List[Dict[str, Any]]] = None,
    failure_count: int = 0,
    monitor_type: Optional[str] = "ping",
) -> Optional[Dict[str, Any]]:
    kind_key = kind if kind in KIND_CHECKS else "other"
    open_ports = tcp_open or []
    hop_note = last_responding_hop(traceroute_hops)
    probe = (monitor_type or "ping").strip().lower()

    if status == "up":
        if rtt_ms is not None and rtt_ms >= warning_rtt_ms:
            unit = "ICMP round-trip time" if probe == "ping" else "probe round-trip time"
            return {
                "code": "latency",
                "title": "Elevated latency",
                "summary": "The endpoint replies, but %s is %s ms (warning threshold %s ms)."
                % (unit, round(rtt_ms, 1), int(warning_rtt_ms)),
                "where": "The path to %s is complete, but it is slow." % host,
                "likely_cause": "Congestion, a distant WAN path, a busy storage controller, or QoS policing of ICMP."
                if probe == "ping"
                else "The service is up, but the probe is taking longer than the warning threshold.",
                "checks": KIND_CHECKS[kind_key][:3]
                + ["Compare latency with a second probe from a jump host on the same VLAN."],
            }
        return None

    if probe and probe != "ping":
        return _monitor_insight(probe, kind_key, host, error, failure_count)

    code = error_code(error)
    if open_ports and code in {"timeout", "filtered", "unknown", "host_unreachable"}:
        code = "icmp_filtered"

    where = {
        "dns": "Failure is in name resolution, before any packet is sent to %s." % host,
        "network": "The Pingwatch host has no usable network path (interface, VRF, or default route).",
        "no_route": "Routing on the Pingwatch host or its gateway has no path toward %s." % host,
        "host_unreachable": "A nearby router or the local subnet reports the host as unreachable (often ARP/ND failure on the last hop).",
        "ttl": "Packets are looping or dying in transit. The destination is probably not receiving them.",
        "filtered": "An ACL, firewall, or control-plane policy is dropping ICMP from Pingwatch.",
        "timeout": "Echo requests left Pingwatch and no reply came back. The drop may be remote, silent, or the endpoint is powered off.",
        "icmp_filtered": "ICMP is blocked or ignored, but the device still answers on TCP %s."
        % ", ".join(str(p) for p in open_ports),
        "unknown": "ICMP did not succeed. See the classified error for the best placement of the fault.",
    }.get(code, "ICMP to %s did not succeed." % host)

    if hop_note:
        where = "%s %s" % (where, hop_note)

    likely = {
        "dns": "Bad hostname, stale DNS record, or resolver failure on the Pingwatch host.",
        "network": "NIC down, missing default route, or the monitoring host is isolated.",
        "no_route": "Wrong gateway, missing static route, or a management VRF is not leaking this prefix.",
        "host_unreachable": "Endpoint is off, unplugged, or the last-hop switch/router cannot ARP it.",
        "ttl": "Routing loop or an incorrect route toward the management prefix.",
        "filtered": "ICMP deny on the device, firewall, or intermediate ACL.",
        "timeout": "Device down, NIC failure, or ICMP silently dropped along the path.",
        "icmp_filtered": "The endpoint is likely still up. ICMP is disabled or filtered; use SSH/HTTPS for confirmation.",
        "unknown": "The endpoint is not answering ICMP from this monitoring host.",
    }.get(code, "The endpoint is not answering ICMP from this monitoring host.")
    if kind_key in {"san", "network"} and code in {"timeout", "filtered", "unknown"}:
        likely = (
            "Many Brocade, Cisco MDS, Cisco IOS, and Aruba management planes disable or rate-limit ICMP. "
            "Treat ping failure as unconfirmed until SSH or HTTPS is also dark."
        )

    title = ERROR_LABELS.get(code, "Unreachable")
    summary = error or title
    if failure_count > 1:
        summary = "%s Repeated %s times in this outage." % (summary.rstrip("."), failure_count)
    if code == "icmp_filtered":
        summary = "ICMP failed, but TCP still answers on port%s %s — treat this as a filter, not a full outage." % (
            "s" if len(open_ports) != 1 else "",
            ", ".join(str(p) for p in open_ports),
        )

    checks = list(KIND_CHECKS[kind_key])
    if code == "dns":
        checks = [
            "Resolve the hostname from the Pingwatch host (getent hosts / nslookup).",
            "Confirm the DNS record still points at the correct management IP.",
            "Try pinging the IP directly to separate DNS failure from device failure.",
        ] + checks[:2]
    elif code == "icmp_filtered":
        checks = [
            "Use SSH or the vendor HTTPS UI — ICMP is not a reliable down signal for this class of device.",
            "Allow ICMP from the Pingwatch host if you want ping to match actual availability.",
        ] + checks[:3]

    return {
        "code": code,
        "title": title,
        "summary": summary,
        "where": where,
        "likely_cause": likely,
        "checks": checks[:6],
    }


INFRA_KINDS = {"storage", "san", "network"}
NOISE_CODES = {"icmp_filtered", "filtered", "latency"}
PATH_CODES = {"host_unreachable", "network", "no_route"}


def issue_priority(
    kind: Optional[str],
    error: Optional[str],
    *,
    failure_count: int = 1,
    tcp_open: Optional[List[int]] = None,
    monitor_type: Optional[str] = "ping",
) -> Dict[str, Any]:
    """Classify an outage as P1/P2/P3 and whether it deserves a ticket."""
    kind_key = kind if kind in KIND_CHECKS else "other"
    insight = build_insight(
        kind_key,
        "",
        status="down",
        error=error,
        tcp_open=tcp_open,
        failure_count=failure_count,
        monitor_type=monitor_type,
    )
    code = (insight or {}).get("code") or "unknown"

    if (monitor_type or "ping") != "ping":
        if kind_key == "storage":
            priority = "P1"
        elif kind_key in {"san", "network"} and code in PATH_CODES:
            priority = "P1"
        else:
            priority = "P2"
        confirmed = failure_count >= 2
        return {
            "priority": priority,
            "code": code,
            "ticket": priority in {"P1", "P2"} and confirmed,
            "confirmed": confirmed,
        }

    if code in NOISE_CODES:
        priority = "P3"
    elif kind_key == "storage" and code in PATH_CODES | {"timeout", "unknown", "ttl"}:
        priority = "P1"
    elif kind_key in {"san", "network"} and code in PATH_CODES:
        priority = "P1"
    elif kind_key in {"san", "network"} and code in {"timeout", "unknown"}:
        priority = "P3"
    elif code in PATH_CODES or code == "dns":
        priority = "P2"
    elif kind_key == "nas" and code in {"timeout", "unknown", "ttl"}:
        priority = "P2"
    elif kind_key == "server" and code in {"timeout", "unknown"}:
        priority = "P2"
    else:
        priority = "P3"

    confirmed = failure_count >= 2
    ticket = (
        priority in {"P1", "P2"}
        and confirmed
        and code not in NOISE_CODES
        and not (
            (monitor_type or "ping") == "ping"
            and kind_key in {"san", "network"}
            and code in {"timeout", "unknown", "filtered"}
        )
    )
    return {"priority": priority, "code": code, "ticket": ticket, "confirmed": confirmed}


def should_open_incident(
    kind: Optional[str],
    error: Optional[str],
    consecutive: int,
    tcp_open: Optional[List[int]] = None,
    monitor_type: Optional[str] = "ping",
) -> bool:
    """Skip one-off flakes and ICMP-only noise on SAN/network gear."""
    if (monitor_type or "ping") != "ping":
        return consecutive >= 2
    verdict = issue_priority(kind, error, failure_count=consecutive, tcp_open=tcp_open, monitor_type=monitor_type)
    if verdict["code"] in {"icmp_filtered", "latency"}:
        return False
    kind_key = kind if kind in KIND_CHECKS else "other"
    if kind_key in {"san", "network"} and verdict["code"] in {"timeout", "filtered", "unknown"}:
        return consecutive >= 3
    return consecutive >= 2


def should_create_ticket(
    kind: Optional[str],
    error: Optional[str],
    failure_count: int,
    existing_sys_id: Optional[str] = None,
    tcp_open: Optional[List[int]] = None,
    monitor_type: Optional[str] = "ping",
) -> bool:
    if existing_sys_id:
        return False
    verdict = issue_priority(
        kind, error, failure_count=failure_count, tcp_open=tcp_open, monitor_type=monitor_type
    )
    return bool(verdict["ticket"])


def short_incident_description(
    name: Optional[str],
    host: Optional[str],
    error: Optional[str],
    *,
    max_len: int = 88,
    monitor_type: Optional[str] = "ping",
) -> str:
    """One-line table/ticket summary: device, host, and probe error."""
    fallback = "Not responding to ICMP" if (monitor_type or "ping") == "ping" else "Monitor is down"
    err = " ".join((error or fallback).split()) or fallback
    label = (name or "CI").strip() or "CI"
    addr = (host or "").strip()
    text = "%s (%s) — %s" % (label, addr, err) if addr else "%s — %s" % (label, err)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
