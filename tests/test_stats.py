from datetime import datetime, timedelta

from app.pinger import classify_ping_error, validate_host
from app.models import Incident, format_incident_number, format_item_id
from app.queries import TABLE_PAGE_SIZE, page_bounds
from app.stats import availability, compute_outages, display_status, downsample, latency_trend, rtt_stats


def test_validate_host_accepts_ip_and_hostname():
    assert validate_host("192.168.1.10") == "192.168.1.10"
    assert validate_host("NAS.LAN") == "nas.lan"


def test_validate_host_rejects_shell_metacharacters():
    try:
        validate_host("evil.com; rm -rf /")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_availability_and_rtt_stats():
    now = datetime(2026, 1, 1, 12, 0, 0)
    rows = [
        {"is_up": True, "rtt_ms": 10, "checked_at": now, "error": None},
        {"is_up": True, "rtt_ms": 30, "checked_at": now, "error": None},
        {"is_up": False, "rtt_ms": None, "checked_at": now, "error": "timeout"},
    ]
    assert availability(rows) == 66.67
    avg, min_rtt, max_rtt = rtt_stats(rows)
    assert avg == 20.0
    assert min_rtt == 10
    assert max_rtt == 30


def test_outages_detect_recovery_and_ongoing():
    start = datetime(2026, 1, 1, 12, 0, 0)
    rows = [
        {"is_up": True, "rtt_ms": 12, "checked_at": start, "error": None},
        {"is_up": False, "rtt_ms": None, "checked_at": start + timedelta(seconds=30), "error": "Request timeout"},
        {"is_up": False, "rtt_ms": None, "checked_at": start + timedelta(seconds=60), "error": "Request timeout"},
        {"is_up": True, "rtt_ms": 14, "checked_at": start + timedelta(seconds=90), "error": None},
        {"is_up": False, "rtt_ms": None, "checked_at": start + timedelta(seconds=120), "error": "DNS resolution failed"},
    ]
    incidents = compute_outages(rows, now=start + timedelta(seconds=150))
    assert len(incidents) == 2
    recovered = [item for item in incidents if not item["ongoing"]][0]
    ongoing = [item for item in incidents if item["ongoing"]][0]
    assert recovered["failure_count"] == 2
    assert recovered["duration_seconds"] == 60
    assert ongoing["last_error"] == "DNS resolution failed"
    assert ongoing["duration_seconds"] == 30


def test_downsample_keeps_last_point():
    points = [{"n": i} for i in range(1000)]
    picked = downsample(points, 10)
    assert len(picked) == 10
    assert picked[-1]["n"] == 999


def test_latency_trend_and_display_status():
    assert latency_trend([10, 11, 10, 40, 42, 41]) == "up"
    assert display_status("up", 12, 200) == "online"
    assert display_status("up", 250, 200) == "warning"
    assert display_status("down", None, 200) == "offline"
    assert classify_ping_error("unknown host foo", 2) == "DNS resolution failed"


def test_incident_number_format():
    assert format_incident_number(1) == "INC0000001"
    assert format_incident_number(42) == "INC0000042"
    assert format_incident_number(100000) == "INC0100000"


def test_item_id_is_six_digits():
    assert format_item_id(1) == "000001"
    assert format_item_id(42) == "000042"
    assert format_item_id(482193) == "482193"


def test_one_active_incident_per_ci():
    column = Incident.__table__.c.active_ci_key
    assert column.unique is True
    assert column.nullable is True


def test_table_page_size_is_fifteen():
    assert TABLE_PAGE_SIZE == 15
    page, size, pages, offset = page_bounds(2, 15, 40)
    assert (page, size, pages, offset) == (2, 15, 3, 15)
    page, size, pages, offset = page_bounds(9, 15, 10)
    assert page == 1
    assert pages == 1
    assert offset == 0
    assert size == 15


def test_fleet_out_includes_monitor_counts():
    from app.schemas import FleetOut

    fleet = FleetOut(
        devices=[],
        total=8,
        filtered_total=8,
        up=7,
        down=1,
        unknown=0,
        warning=0,
        last_sweep_at=None,
        page=1,
        page_size=25,
        pages=1,
        monitor_counts={"ping": 6, "dns": 2},
    )
    assert fleet.monitor_counts == {"ping": 6, "dns": 2}
