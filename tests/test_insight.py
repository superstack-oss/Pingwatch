from app.insight import (
    build_insight,
    classify_from_output,
    issue_priority,
    last_responding_hop,
    should_create_ticket,
    should_open_incident,
    short_incident_description,
)
from app.pinger import classify_ping_error


def test_classify_dns_timeout_and_host_unreachable():
    assert classify_ping_error("unknown host foo", 2) == "DNS resolution failed"
    assert classify_from_output("ping: nas.lab: Name or service not known", 2) == "DNS resolution failed"
    assert classify_from_output("From 10.0.0.1 icmp_seq=1 Destination Host Unreachable", 1) == "Host unreachable"
    assert classify_from_output("connect: Network is unreachable", 2) == "Network unreachable"
    assert classify_from_output("From 10.0.0.1 icmp_seq=1 Time to live exceeded", 1) == "TTL exceeded"
    assert classify_from_output("From 10.0.0.1 icmp_seq=1 Communication administratively prohibited", 1) == (
        "ICMP administratively filtered"
    )
    assert classify_from_output("1 packets transmitted, 0 received, 100% packet loss", 1) == "Request timeout"
    assert classify_from_output("No route to host", 1) == "No route to host"


def test_insight_for_storage_timeout():
    insight = build_insight("storage", "10.10.8.21", status="down", error="Request timeout")
    assert insight["code"] == "timeout"
    assert insight["where"].startswith("Echo requests")
    assert any("Unisphere" in item or "ONTAP" in item or "SSMC" in item for item in insight["checks"])


def test_san_timeout_is_unconfirmed_until_tcp():
    insight = build_insight("san", "10.20.30.4", status="down", error="Request timeout")
    assert "ICMP" in insight["likely_cause"]
    assert any("Brocade" in item or "SSH" in item for item in insight["checks"])


def test_icmp_filtered_when_tcp_still_answers():
    insight = build_insight(
        "network",
        "core-sw.lab",
        status="down",
        error="Request timeout",
        tcp_open=[22, 443],
    )
    assert insight["code"] == "icmp_filtered"
    assert "22" in insight["summary"]
    assert "filter" in insight["summary"].lower()


def test_latency_insight_when_up_but_slow():
    insight = build_insight("server", "app01", status="up", rtt_ms=280, warning_rtt_ms=200)
    assert insight["code"] == "latency"
    assert build_insight("server", "app01", status="up", rtt_ms=12, warning_rtt_ms=200) is None


def test_priority_and_ticket_gates():
    storage = issue_priority("storage", "Request timeout", failure_count=2)
    assert storage["priority"] == "P1"
    assert storage["ticket"] is True
    san_timeout = issue_priority("san", "Request timeout", failure_count=5)
    assert san_timeout["priority"] == "P3"
    assert san_timeout["ticket"] is False
    san_dead = issue_priority("san", "Host unreachable", failure_count=2)
    assert san_dead["priority"] == "P1"
    assert san_dead["ticket"] is True
    server = issue_priority("server", "Request timeout", failure_count=2)
    assert server["priority"] == "P2"
    filtered = issue_priority("network", "Request timeout", failure_count=4, tcp_open=[22, 443])
    assert filtered["priority"] == "P3"
    assert filtered["ticket"] is False


def test_open_incident_skips_flakes_and_icmp_noise():
    assert should_open_incident("server", "Request timeout", 1) is False
    assert should_open_incident("server", "Request timeout", 2) is True
    assert should_open_incident("san", "Request timeout", 2) is False
    assert should_open_incident("san", "Request timeout", 3) is True
    assert should_open_incident("network", "Request timeout", 4, tcp_open=[443]) is False
    assert should_open_incident("server", "TCP handshake failed", 2, monitor_type="tcp") is True
    assert should_open_incident("san", "TCP handshake failed", 2, monitor_type="tcp") is True


def test_no_duplicate_ticket_when_one_already_exists():
    assert should_create_ticket("storage", "Request timeout", 4, existing_sys_id="abc") is False
    assert should_create_ticket("storage", "Request timeout", 1) is False
    assert should_create_ticket("storage", "Request timeout", 2) is True
    assert should_create_ticket("san", "Request timeout", 8) is False


def test_last_responding_hop_describes_break():
    hops = [
        {"hop": 1, "host": "10.0.0.1"},
        {"hop": 2, "host": "10.1.1.1"},
        {"hop": 3, "host": None},
        {"hop": 4, "host": None},
    ]
    note = last_responding_hop(hops)
    assert "hop 2" in note
    assert "beyond" in note.lower()


def test_short_incident_description_stays_on_one_line():
    text = short_incident_description("Unreachable test", "192.8.2.1", "Request timeout")
    assert text == "Unreachable test (192.8.2.1) — Request timeout"
    assert "\n" not in text
    long_error = "Request timeout. Repeated 13 times in this outage. Where: Echo requests left Pingwatch."
    short = short_incident_description("Unreachable test", "192.8.2.1", long_error)
    assert "\n" not in short
    assert len(short) <= 88
    assert short.endswith("…")
