from app.dnscheck import ipv4_addresses
from app.game_types import GAMES, game_info, normalize_game_id
from app.monitors import (
    build_monitor_key,
    catalog,
    monitor_label,
    normalize_monitor,
    target_display,
)


def test_ipv4_addresses_skips_v6():
    assert ipv4_addresses(["167.239.226.37", "2001:db8::1"]) == ["167.239.226.37"]
    assert ipv4_addresses([]) == []


def test_game_catalog_covers_more_than_100_types():
    assert len(GAMES) >= 100
    assert catalog()["game_count"] >= 100
    assert normalize_game_id("CS2") == "cs2"
    assert game_info("minecraft")[1] == "minecraft"
    assert game_info("gmod")[0] == "Garry's Mod"


def test_ping_is_the_default_monitor():
    target = normalize_monitor(host="192.168.1.10")
    assert target.monitor_type == "ping"
    assert target.port is None
    assert target.key == build_monitor_key("ping", "192.168.1.10", None, {})
    assert monitor_label("ping") == "Ping"
    assert target_display("ping", "aep.com", None, {"resolved_ip": "167.239.226.37"}) == "aep.com (167.239.226.37)"


def test_tcp_requires_port_and_is_unique_per_port():
    ssh = normalize_monitor(host="db.lab.local", monitor_type="tcp", port=22)
    mysql = normalize_monitor(host="db.lab.local", monitor_type="TCP Port", port=3306)
    assert ssh.monitor_type == "tcp"
    assert ssh.port == 22
    assert ssh.key != mysql.key
    try:
        normalize_monitor(host="db.lab.local", monitor_type="tcp")
    except ValueError as exc:
        assert "Port" in str(exc)
        return
    raise AssertionError("expected port error")


def test_dns_monitor_uses_resolver_and_record_type():
    target = normalize_monitor(
        host="internal.lab",
        monitor_type="dns",
        dns_qtype="AAAA",
        dns_nameserver="1.1.1.1",
    )
    assert target.spec["qtype"] == "AAAA"
    assert target.spec["nameserver"] == "1.1.1.1"
    assert "dns" in target.key
    assert "AAAA" in target_display("dns", target.host, None, target.spec)


def test_websocket_parses_wss_url():
    target = normalize_monitor(host="wss://chat.example.com/socket", monitor_type="websocket")
    assert target.host == "chat.example.com"
    assert target.port == 443
    assert target.spec["path"] == "/socket"
    assert target.spec["secure"] is True
    assert target_display("websocket", target.host, target.port, target.spec).startswith("wss://")


def test_grpc_and_game_defaults():
    grpc = normalize_monitor(host="api.lab.local", monitor_type="grpc", grpc_service="orders.v1.Orders")
    assert grpc.port == 50051
    assert grpc.spec["service"] == "orders.v1.Orders"
    game = normalize_monitor(host="game.lab.local", monitor_type="game", game_type="valheim")
    assert game.spec["game_type"] == "valheim"
    assert game.port == 2456
