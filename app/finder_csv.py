from __future__ import annotations

import csv
import io
import re
from typing import Dict, List, Optional, Tuple

from app.monitors import dump_spec, normalize_monitor

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000

SHARE_TEMPLATE = (
    "Seq No,Name,Path,Description,Storage\r\n"
    "1,Projects,/volume1/projects,Team project share,Studio NAS\r\n"
    "2,Backups,/volume1/backups,Nightly backup target,Studio NAS\r\n"
)

VOLUME_TEMPLATE = (
    "Seq No,Name,WWN,Size,Storage\r\n"
    "1,VM-Datastore,6000c29a1b2c3d4e5f60718293a4b5c6,2 TB,Primary SAN\r\n"
    "2,Media-Pool,5000cca264d3ab12,40 TB,Archive NAS\r\n"
)

DEVICE_TEMPLATE = (
    "Display name,Host or IP,Type,Monitor,Port,Notes\r\n"
    "Studio NAS,192.168.1.10,NAS,Ping,,Rack A\r\n"
    "Core switch,core.lab.local,Network,Ping,,\r\n"
    "App server,10.0.0.21,Server,Ping,,Production\r\n"
    "Mail,mail.lab.local,Server,TCP Port,25,\r\n"
    "Internal zone,internal.lab,Network,DNS,,\r\n"
)

MAX_DEVICE_ROWS = 500

KIND_ALIASES = {
    "nas": "nas",
    "nasserver": "nas",
    "storage": "storage",
    "storagearray": "storage",
    "array": "storage",
    "san": "san",
    "network": "network",
    "switch": "network",
    "router": "network",
    "firewall": "network",
    "server": "server",
    "srv": "server",
    "other": "other",
}

SHARE_ALIASES = {
    "seqno": "seq_no",
    "seq": "seq_no",
    "sequence": "seq_no",
    "sequenceno": "seq_no",
    "sequencenumber": "seq_no",
    "name": "name",
    "sharename": "name",
    "share": "name",
    "path": "path",
    "sharepath": "path",
    "mount": "path",
    "mountpath": "path",
    "description": "description",
    "desc": "description",
    "notes": "description",
    "storage": "storage",
    "nas": "storage",
    "array": "storage",
    "storagearray": "storage",
}

DEVICE_ALIASES = {
    "displayname": "name",
    "name": "name",
    "device": "name",
    "devicename": "name",
    "hostorip": "host",
    "host": "host",
    "hostname": "host",
    "ip": "host",
    "ipaddress": "host",
    "address": "host",
    "type": "kind",
    "kind": "kind",
    "devicetype": "kind",
    "notes": "notes",
    "note": "notes",
    "comment": "notes",
    "comments": "notes",
    "monitor": "monitor_type",
    "monitortype": "monitor_type",
    "probe": "monitor_type",
    "check": "monitor_type",
    "port": "port",
    "tcpport": "port",
    "queryport": "port",
    "record": "dns_qtype",
    "qtype": "dns_qtype",
    "recordtype": "dns_qtype",
    "resolver": "dns_nameserver",
    "nameserver": "dns_nameserver",
    "dns": "dns_nameserver",
    "path": "ws_path",
    "wspath": "ws_path",
    "game": "game_type",
    "gametype": "game_type",
    "gameserver": "game_type",
    "grpcservice": "grpc_service",
    "service": "grpc_service",
}

VOLUME_ALIASES = {
    "seqno": "seq_no",
    "seq": "seq_no",
    "sequence": "seq_no",
    "sequenceno": "seq_no",
    "sequencenumber": "seq_no",
    "name": "name",
    "volumename": "name",
    "volume": "name",
    "lun": "name",
    "wwn": "wwn",
    "wwpn": "wwn",
    "worldwidename": "wwn",
    "serial": "wwn",
    "size": "size",
    "capacity": "size",
    "sizegb": "size",
    "storage": "storage",
    "array": "storage",
    "storagearray": "storage",
}


class CsvError(ValueError):
    pass


def _norm_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _clean(value: Optional[str], limit: int) -> str:
    text = " ".join(str(value or "").replace("\x00", "").split())
    return text[:limit]


def _seq_no(raw: str, fallback: int) -> int:
    digits = re.sub(r"[^\d]", "", raw or "")
    if digits:
        try:
            return int(digits)
        except ValueError:
            pass
    return fallback


def _decode(payload: bytes) -> str:
    if len(payload) > MAX_UPLOAD_BYTES:
        raise CsvError("CSV is larger than 2 MB")
    if payload.startswith(b"\xff\xfe") or payload.startswith(b"\xfe\xff"):
        raise CsvError("Upload a UTF-8 or Excel CSV file")
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", "replace")


def _reader(text: str) -> csv.DictReader:
    sample = text.lstrip("\ufeff")
    if not sample.strip():
        raise CsvError("The CSV file is empty")
    try:
        dialect = csv.Sniffer().sniff(sample[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    stream = io.StringIO(sample)
    reader = csv.DictReader(stream, dialect=dialect)
    if not reader.fieldnames:
        raise CsvError("The CSV file is missing a header row")
    return reader


def _mapped_fields(fieldnames: List[Optional[str]], aliases: Dict[str, str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for raw in fieldnames:
        key = aliases.get(_norm_header(raw or ""))
        if key and key not in mapping:
            mapping[key] = raw or ""
    return mapping


def parse_share_csv(payload: bytes) -> Tuple[List[Dict], List[str]]:
    reader = _reader(_decode(payload))
    mapping = _mapped_fields(list(reader.fieldnames or []), SHARE_ALIASES)
    missing = [label for label in ("name", "path") if label not in mapping]
    if missing:
        raise CsvError("NAS CSV must include Name and Path columns")
    rows: List[Dict] = []
    errors: List[str] = []
    seen = set()
    for index, item in enumerate(reader, start=2):
        if len(rows) >= MAX_ROWS:
            errors.append("Stopped after %s rows" % MAX_ROWS)
            break
        name = _clean(item.get(mapping["name"]), 190)
        path = _clean(item.get(mapping["path"]), 500)
        if not name and not path:
            continue
        if not name or not path:
            errors.append("Row %s needs both Name and Path" % index)
            continue
        key = path.lower()
        if key in seen:
            errors.append("Row %s skipped duplicate path %s" % (index, path))
            continue
        seen.add(key)
        seq_raw = item.get(mapping["seq_no"], "") if "seq_no" in mapping else ""
        rows.append(
            {
                "seq_no": _seq_no(str(seq_raw), len(rows) + 1),
                "name": name,
                "path": path,
                "description": _clean(item.get(mapping["description"]), 2000) if "description" in mapping else "",
                "storage": _clean(item.get(mapping["storage"]), 190) if "storage" in mapping else "",
            }
        )
    if not rows:
        raise CsvError("No valid NAS share rows were found")
    return rows, errors


def parse_volume_csv(payload: bytes) -> Tuple[List[Dict], List[str]]:
    reader = _reader(_decode(payload))
    mapping = _mapped_fields(list(reader.fieldnames or []), VOLUME_ALIASES)
    missing = [label for label in ("name", "wwn") if label not in mapping]
    if missing:
        raise CsvError("Volume CSV must include Name and WWN columns")
    rows: List[Dict] = []
    errors: List[str] = []
    seen = set()
    for index, item in enumerate(reader, start=2):
        if len(rows) >= MAX_ROWS:
            errors.append("Stopped after %s rows" % MAX_ROWS)
            break
        name = _clean(item.get(mapping["name"]), 190)
        wwn = _clean(item.get(mapping["wwn"]), 128)
        if not name and not wwn:
            continue
        if not name or not wwn:
            errors.append("Row %s needs both Name and WWN" % index)
            continue
        key = wwn.lower()
        if key in seen:
            errors.append("Row %s skipped duplicate WWN %s" % (index, wwn))
            continue
        seen.add(key)
        seq_raw = item.get(mapping["seq_no"], "") if "seq_no" in mapping else ""
        rows.append(
            {
                "seq_no": _seq_no(str(seq_raw), len(rows) + 1),
                "name": name,
                "wwn": wwn,
                "size": _clean(item.get(mapping["size"]), 64) if "size" in mapping else "",
                "storage": _clean(item.get(mapping["storage"]), 190) if "storage" in mapping else "",
            }
        )
    if not rows:
        raise CsvError("No valid volume rows were found")
    return rows, errors


def _parse_kind(raw: str) -> Optional[str]:
    return KIND_ALIASES.get(_norm_header(raw))


def parse_device_csv(payload: bytes) -> Tuple[List[Dict], List[str]]:
    reader = _reader(_decode(payload))
    mapping = _mapped_fields(list(reader.fieldnames or []), DEVICE_ALIASES)
    missing = [label for label in ("name", "host", "kind") if label not in mapping]
    if missing:
        raise CsvError("Device CSV must include Display name, Host or IP, and Type columns")
    rows: List[Dict] = []
    errors: List[str] = []
    seen = set()
    for index, item in enumerate(reader, start=2):
        if len(rows) >= MAX_DEVICE_ROWS:
            errors.append("Stopped after %s rows" % MAX_DEVICE_ROWS)
            break
        name = _clean(item.get(mapping["name"]), 120)
        host_raw = _clean(item.get(mapping["host"]), 253)
        kind_raw = _clean(item.get(mapping["kind"]), 32)
        notes = _clean(item.get(mapping["notes"]), 500) if "notes" in mapping else ""
        if not name and not host_raw and not kind_raw:
            continue
        if not name or not host_raw or not kind_raw:
            errors.append("Row %s needs Display name, Host or IP, and Type" % index)
            continue
        kind = _parse_kind(kind_raw)
        if not kind:
            errors.append("Row %s has unknown type %s" % (index, kind_raw))
            continue
        monitor_raw = _clean(item.get(mapping["monitor_type"]), 32) if "monitor_type" in mapping else "ping"
        port_raw = _clean(item.get(mapping["port"]), 8) if "port" in mapping else ""
        try:
            target = normalize_monitor(
                host=host_raw,
                monitor_type=monitor_raw or "ping",
                port=port_raw or None,
                dns_qtype=_clean(item.get(mapping["dns_qtype"]), 16) if "dns_qtype" in mapping else None,
                dns_nameserver=_clean(item.get(mapping["dns_nameserver"]), 253) if "dns_nameserver" in mapping else None,
                ws_path=_clean(item.get(mapping["ws_path"]), 200) if "ws_path" in mapping else None,
                grpc_service=_clean(item.get(mapping["grpc_service"]), 190) if "grpc_service" in mapping else None,
                game_type=_clean(item.get(mapping["game_type"]), 64) if "game_type" in mapping else None,
            )
        except ValueError as exc:
            message = str(exc)
            if "hostname" in message.lower() or "host or ip" in message.lower() or "websocket url" in message.lower():
                errors.append("Row %s has an invalid host or IP" % index)
            else:
                errors.append("Row %s %s" % (index, message))
            continue
        if target.key in seen:
            errors.append("Row %s skipped duplicate host %s" % (index, target.host))
            continue
        seen.add(target.key)
        rows.append(
            {
                "name": name,
                "host": target.host,
                "kind": kind,
                "notes": notes or None,
                "monitor_type": target.monitor_type,
                "port": target.port,
                "monitor_spec": dump_spec(target.spec),
                "monitor_key": target.key,
            }
        )
    if not rows:
        raise CsvError("No valid device rows were found")
    return rows, errors
