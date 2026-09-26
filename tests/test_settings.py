from app.settings_store import (
    PING_INTERVAL_CHOICES,
    clamp_ping_interval,
    clean_company_name,
    public_settings,
    setting_flag,
)


def test_live_and_long_ping_durations_are_allowed():
    assert 1 in PING_INTERVAL_CHOICES
    assert 30 in PING_INTERVAL_CHOICES
    assert 3600 in PING_INTERVAL_CHOICES
    assert 43200 in PING_INTERVAL_CHOICES
    assert 259200 in PING_INTERVAL_CHOICES
    assert clamp_ping_interval(1) == 1
    assert clamp_ping_interval("259200") == 259200
    assert clamp_ping_interval(15) in PING_INTERVAL_CHOICES


def test_incidents_flag_defaults_on():
    assert setting_flag({}, "incidents_enabled", True) is True
    assert setting_flag({"incidents_enabled": "false"}, "incidents_enabled") is False
    assert setting_flag({"incidents_enabled": "true"}, "incidents_enabled") is True
    pub = public_settings({"incidents_enabled": "false", "ping_interval": "30", "timezone": "UTC"})
    assert pub["incidents_enabled"] is False
    assert pub["ping_interval"] == 30
    assert pub["company_name"] == ""


def test_company_name_is_trimmed_to_15_characters():
    assert clean_company_name("  Superstack  ") == "Superstack"
    assert clean_company_name("ABCDEFGHIJKLMNOPQR") == "ABCDEFGHIJKLMNO"
    pub = public_settings({"company_name": "  Superstack  ", "ping_interval": "30"})
    assert pub["company_name"] == "Superstack"


def test_version_file_matches_public_settings():
    from pathlib import Path

    version = Path("VERSION").read_text(encoding="utf-8").strip()
    assert version
    assert public_settings({})["version"] == version
