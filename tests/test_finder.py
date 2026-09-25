from app.finder_csv import (
    DEVICE_TEMPLATE,
    SHARE_TEMPLATE,
    VOLUME_TEMPLATE,
    CsvError,
    parse_device_csv,
    parse_share_csv,
    parse_volume_csv,
)


def test_parse_share_template():
    rows, warnings = parse_share_csv(SHARE_TEMPLATE.encode("utf-8"))
    assert warnings == []
    assert len(rows) == 2
    assert rows[0]["seq_no"] == 1
    assert rows[0]["name"] == "Projects"
    assert rows[0]["path"] == "/volume1/projects"
    assert rows[1]["storage"] == "Studio NAS"


def test_parse_volume_template():
    rows, warnings = parse_volume_csv(VOLUME_TEMPLATE.encode("utf-8"))
    assert len(rows) == 2
    assert rows[0]["wwn"] == "6000c29a1b2c3d4e5f60718293a4b5c6"
    assert rows[0]["size"] == "2 TB"
    assert rows[1]["name"] == "Media-Pool"


def test_share_csv_accepts_aliases_and_semicolon():
    payload = "Share Name;Mount Path;Notes;Array\nMedia;/share/media;Video;NAS-01\n".encode("utf-8")
    rows, _warnings = parse_share_csv(payload)
    assert rows[0]["name"] == "Media"
    assert rows[0]["path"] == "/share/media"
    assert rows[0]["description"] == "Video"
    assert rows[0]["storage"] == "NAS-01"


def test_volume_csv_requires_name_and_wwn():
    try:
        parse_volume_csv(b"Name,Size\nDisk,1 TB\n")
    except CsvError as exc:
        assert "WWN" in str(exc)
        return
    raise AssertionError("expected CsvError")


def test_share_csv_skips_blank_and_duplicate_paths():
    payload = (
        "Seq No,Name,Path,Description,Storage\n"
        "1,One,/vol/one,First,NAS\n"
        "2,Two,/vol/one,Dup,NAS\n"
        ",,,,\n"
    ).encode("utf-8")
    rows, warnings = parse_share_csv(payload)
    assert len(rows) == 1
    assert rows[0]["name"] == "One"
    assert warnings and "duplicate" in warnings[0]


def test_empty_csv_rejected():
    try:
        parse_share_csv(b"Name,Path\n")
    except CsvError:
        return
    raise AssertionError("expected CsvError")


def test_parse_device_template():
    rows, warnings = parse_device_csv(DEVICE_TEMPLATE.encode("utf-8"))
    assert warnings == []
    assert len(rows) == 5
    assert rows[0]["name"] == "Studio NAS"
    assert rows[0]["host"] == "192.168.1.10"
    assert rows[0]["kind"] == "nas"
    assert rows[0]["monitor_type"] == "ping"
    assert rows[0]["notes"] == "Rack A"
    assert rows[1]["kind"] == "network"
    assert rows[1]["notes"] is None
    assert rows[2]["kind"] == "server"
    assert rows[3]["monitor_type"] == "tcp"
    assert rows[3]["port"] == 25
    assert rows[4]["monitor_type"] == "dns"


def test_device_csv_skips_bad_host_and_duplicate():
    payload = (
        "Display name,Host or IP,Type,Notes\n"
        "One,192.168.1.10,Server,\n"
        "Two,192.168.1.10,NAS,\n"
        "Bad,not a host!!,Server,\n"
        "No type,10.0.0.8,,\n"
    ).encode("utf-8")
    rows, warnings = parse_device_csv(payload)
    assert len(rows) == 1
    assert rows[0]["host"] == "192.168.1.10"
    assert any("duplicate" in item for item in warnings)
    assert any("invalid host" in item for item in warnings)
    assert any("Display name, Host or IP, and Type" in item for item in warnings)


def test_device_csv_allows_same_host_different_monitors():
    payload = (
        "Display name,Host or IP,Type,Monitor,Port,Notes\n"
        "Ping,10.0.0.8,Server,Ping,,\n"
        "SSH,10.0.0.8,Server,TCP Port,22,\n"
    ).encode("utf-8")
    rows, warnings = parse_device_csv(payload)
    assert warnings == []
    assert len(rows) == 2
    assert rows[0]["monitor_type"] == "ping"
    assert rows[1]["monitor_type"] == "tcp"
    assert rows[1]["port"] == 22
    assert rows[0]["monitor_key"] != rows[1]["monitor_key"]
