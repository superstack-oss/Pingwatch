from __future__ import annotations

import json
from typing import Any, Dict, NamedTuple, Optional
from urllib.parse import urlparse

from app.checks_dns import DNS_TYPES, query_resolver
from app.checks_game import check_game
from app.checks_grpc import check_grpc
from app.checks_ws import check_websocket
from app.game_types import GAMES, game_choices, game_info, normalize_game_id
from app.netcheck import check_tcp
from app.pinger import PingOutcome, ping_host, validate_host

MONITOR_TYPES = ("ping", "tcp", "dns", "websocket", "grpc", "game")

MONITOR_LABELS = {
    "ping": "Ping",
    "tcp": "TCP Port",
    "dns": "DNS",
    "websocket": "WebSocket",
    "grpc": "gRPC",
    "game": "Game server",
}

MONITOR_ALIASES = {
    "ping": "ping",
    "icmp": "ping",
    "tcp": "tcp",
    "tcpport": "tcp",
    "port": "tcp",
    "dns": "dns",
    "websocket": "websocket",
    "ws": "websocket",
    "wss": "websocket",
    "grpc": "grpc",
    "grpcmonitoring": "grpc",
    "health": "grpc",
    "game": "game",
    "gameserver": "game",
    "gamedig": "game",
}

DEFAULT_PORTS = {
    "tcp": 443,
    "websocket": 80,
    "grpc": 50051,
}

DOWN_PHRASES = {
    "ping": "Not responding to ICMP",
    "tcp": "TCP handshake failed",
    "dns": "DNS lookup failed",
    "websocket": "WebSocket handshake failed",
    "grpc": "gRPC health is not SERVING",
    "game": "Game server query failed",
}


class MonitorTarget(NamedTuple):
    monitor_type: str
    host: str
    port: Optional[int]
    spec: Dict[str, Any]
    key: str


def empty_to_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def parse_spec(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def dump_spec(spec: Optional[Dict[str, Any]]) -> Optional[str]:
    data = {key: value for key, value in (spec or {}).items() if value not in (None, "", [])}
    return json.dumps(data, separators=(",", ":")) if data else None


def monitor_label(monitor_type: Optional[str]) -> str:
    return MONITOR_LABELS.get((monitor_type or "ping").strip().lower(), MONITOR_LABELS["ping"])


def down_phrase(monitor_type: Optional[str], error: Optional[str] = None) -> str:
    if error and error.strip():
        return " ".join(error.split())
    return DOWN_PHRASES.get((monitor_type or "ping").strip().lower(), "Monitor is down")


def normalize_monitor_type(value: Optional[str]) -> str:
    key = "".join(ch for ch in (value or "ping").lower() if ch.isalnum())
    mapped = MONITOR_ALIASES.get(key or "ping")
    if not mapped:
        raise ValueError("Unknown monitor type")
    return mapped


def _port(value: Any, required: bool = False, default: Optional[int] = None) -> Optional[int]:
    value = empty_to_none(value)
    if value is None:
        if required and default is None:
            raise ValueError("Port is required")
        return default
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Port must be a number") from exc
    if port < 1 or port > 65535:
        raise ValueError("Port must be between 1 and 65535")
    return port


def _ws_from_url(raw: str) -> Optional[Dict[str, Any]]:
    text = raw.strip()
    if not text.lower().startswith(("ws://", "wss://")):
        return None
    parsed = urlparse(text)
    if not parsed.hostname:
        raise ValueError("Enter a valid WebSocket URL")
    secure = parsed.scheme.lower() == "wss"
    port = parsed.port or (443 if secure else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = "%s?%s" % (path, parsed.query)
    return {"host": parsed.hostname, "port": port, "path": path, "secure": secure}


def build_monitor_key(monitor_type: str, host: str, port: Optional[int], spec: Dict[str, Any]) -> str:
    extra = ""
    if monitor_type == "dns":
        extra = "%s:%s" % (spec.get("nameserver") or "system", spec.get("qtype") or "A")
    elif monitor_type == "websocket":
        extra = "%s:%s" % (spec.get("path") or "/", "s" if spec.get("secure") else "p")
    elif monitor_type == "grpc":
        extra = spec.get("service") or ""
    elif monitor_type == "game":
        extra = spec.get("game_type") or ""
    return ("%s|%s|%s|%s" % (monitor_type, host, port or "", extra))[:190]


def target_display(monitor_type: str, host: str, port: Optional[int], spec: Optional[Dict[str, Any]] = None) -> str:
    spec = spec or {}
    if monitor_type == "tcp":
        return "%s:%s" % (host, port)
    if monitor_type == "dns":
        qtype = spec.get("qtype") or "A"
        nameserver = spec.get("nameserver")
        return "%s (%s) via %s" % (host, qtype, nameserver or "system resolver")
    if monitor_type == "websocket":
        scheme = "wss" if spec.get("secure") else "ws"
        return "%s://%s:%s%s" % (scheme, host, port, spec.get("path") or "/")
    if monitor_type == "grpc":
        service = spec.get("service")
        return "%s:%s/%s" % (host, port, service) if service else "%s:%s" % (host, port)
    if monitor_type == "game":
        info = game_info(str(spec.get("game_type") or ""))
        label = info[0] if info else spec.get("game_type") or "game"
        return "%s:%s (%s)" % (host, port, label)
    return host


def catalog() -> Dict[str, Any]:
    return {
        "types": [{"id": key, "label": MONITOR_LABELS[key]} for key in MONITOR_TYPES],
        "dns_types": list(DNS_TYPES),
        "games": game_choices(),
        "game_count": len(GAMES),
    }


def normalize_monitor(
    *,
    host: str,
    monitor_type: Optional[str] = "ping",
    port: Any = None,
    dns_qtype: Optional[str] = None,
    dns_nameserver: Optional[str] = None,
    ws_path: Optional[str] = None,
    ws_secure: Any = None,
    grpc_service: Optional[str] = None,
    game_type: Optional[str] = None,
    spec: Optional[Dict[str, Any]] = None,
) -> MonitorTarget:
    kind = normalize_monitor_type(monitor_type)
    spec = dict(spec or {})
    ws = _ws_from_url(host)
    if ws:
        if kind != "websocket":
            kind = "websocket"
        host = ws["host"]
        port = port or ws["port"]
        spec["path"] = spec.get("path") or ws["path"]
        spec["secure"] = True if spec.get("secure") else ws["secure"]
    host = validate_host(host)

    if kind == "ping":
        return MonitorTarget(kind, host, None, {}, build_monitor_key(kind, host, None, {}))

    if kind == "tcp":
        port_n = _port(port, required=True)
        return MonitorTarget(kind, host, port_n, {}, build_monitor_key(kind, host, port_n, {}))

    if kind == "dns":
        qtype = (empty_to_none(dns_qtype) or spec.get("qtype") or "A").strip().upper()
        if qtype not in DNS_TYPES:
            raise ValueError("DNS record type must be one of %s" % ", ".join(DNS_TYPES))
        nameserver = empty_to_none(dns_nameserver) or spec.get("nameserver")
        if nameserver:
            nameserver = validate_host(str(nameserver))
        data = {"qtype": qtype}
        if nameserver:
            data["nameserver"] = nameserver
        return MonitorTarget(kind, host, None, data, build_monitor_key(kind, host, None, data))

    if kind == "websocket":
        secure = spec.get("secure")
        if ws_secure is not None:
            if isinstance(ws_secure, str):
                secure = ws_secure.strip().lower() in {"1", "true", "yes", "on", "wss"}
            else:
                secure = bool(ws_secure)
        path = empty_to_none(ws_path) or spec.get("path") or "/"
        if not str(path).startswith("/"):
            path = "/" + str(path)
        port_n = _port(port, default=443 if secure else 80)
        data = {"path": path, "secure": bool(secure)}
        return MonitorTarget(kind, host, port_n, data, build_monitor_key(kind, host, port_n, data))

    if kind == "grpc":
        port_n = _port(port, default=DEFAULT_PORTS["grpc"])
        service = empty_to_none(grpc_service) or spec.get("service")
        data = {"service": service} if service else {}
        return MonitorTarget(kind, host, port_n, data, build_monitor_key(kind, host, port_n, data))

    game_id = normalize_game_id(str(empty_to_none(game_type) or spec.get("game_type") or ""))
    if not game_id:
        raise ValueError("Choose a game type")
    info = game_info(game_id)
    port_n = _port(port, default=info[2] if info else None)
    data = {"game_type": game_id}
    return MonitorTarget(kind, host, port_n, data, build_monitor_key(kind, host, port_n, data))


def target_from_device(device: Any) -> MonitorTarget:
    return normalize_monitor(
        host=device.host,
        monitor_type=getattr(device, "monitor_type", None) or "ping",
        port=getattr(device, "port", None),
        spec=parse_spec(getattr(device, "monitor_spec", None)),
    )


def apply_monitor_fields(device: Any, incoming: Dict[str, Any]) -> MonitorTarget:
    current = parse_spec(getattr(device, "monitor_spec", None))
    host = incoming.get("host", device.host)
    monitor_type = incoming.get("monitor_type", getattr(device, "monitor_type", None) or "ping")
    port = incoming["port"] if "port" in incoming else getattr(device, "port", None)
    target = normalize_monitor(
        host=host,
        monitor_type=monitor_type,
        port=port,
        dns_qtype=incoming.get("dns_qtype", current.get("qtype")),
        dns_nameserver=incoming.get("dns_nameserver", current.get("nameserver")),
        ws_path=incoming.get("ws_path", current.get("path")),
        ws_secure=incoming.get("ws_secure", current.get("secure")),
        grpc_service=incoming.get("grpc_service", current.get("service")),
        game_type=incoming.get("game_type", current.get("game_type")),
        spec=current,
    )
    device.host = target.host
    device.monitor_type = target.monitor_type
    device.port = target.port
    device.monitor_spec = dump_spec(target.spec)
    device.monitor_key = target.key
    return target


async def probe_device(device: Any, timeout: float) -> PingOutcome:
    try:
        target = target_from_device(device)
        if target.monitor_type == "ping":
            return await ping_host(target.host, timeout)
        if target.monitor_type == "tcp":
            result = await check_tcp(target.host, int(target.port or 0), timeout)
            if result.get("open"):
                return PingOutcome(True, result.get("elapsed_ms"), None)
            return PingOutcome(False, None, "TCP handshake failed on port %s" % target.port)
        if target.monitor_type == "dns":
            return await query_resolver(
                target.host,
                qtype=str(target.spec.get("qtype") or "A"),
                nameserver=target.spec.get("nameserver"),
                timeout=timeout,
            )
        if target.monitor_type == "websocket":
            return await check_websocket(
                target.host,
                int(target.port or (443 if target.spec.get("secure") else 80)),
                path=str(target.spec.get("path") or "/"),
                secure=bool(target.spec.get("secure")),
                timeout=timeout,
            )
        if target.monitor_type == "grpc":
            return await check_grpc(
                target.host,
                int(target.port or 50051),
                service=target.spec.get("service"),
                timeout=timeout,
            )
        if target.monitor_type == "game":
            return await check_game(
                target.host,
                int(target.port or 0),
                str(target.spec.get("game_type") or ""),
                timeout=timeout,
            )
        return PingOutcome(False, None, "Unknown monitor type")
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "Probe failed")
