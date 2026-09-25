from __future__ import annotations

import asyncio
import platform
import time
from typing import Any, Dict, List, Optional

from app.insight import KIND_PORTS, build_insight
from app.pinger import ping_host, validate_host

COMMON_PORTS = (22, 80, 443, 445, 548, 139, 111, 2049, 5000, 5001)


async def check_tcp(host: str, port: int, timeout: float = 1.2) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        del reader
        return {
            "port": port,
            "open": True,
            "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 2),
            "error": None,
        }
    except Exception as exc:
        return {
            "port": port,
            "open": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 2),
            "error": exc.__class__.__name__,
        }


def _traceroute_command(host: str) -> Optional[List[str]]:
    system = platform.system()
    if system == "Darwin":
        return ["traceroute", "-n", "-w", "1", "-m", "12", host]
    if system == "Windows":
        return ["tracert", "-d", "-w", "1000", "-h", "12", host]
    return ["traceroute", "-n", "-w", "1", "-m", "12", "-q", "1", host]


def _parse_hops(output: str) -> List[Dict[str, Any]]:
    hops: List[Dict[str, Any]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith(("traceroute", "tracing")):
            continue
        parts = stripped.split()
        if not parts:
            continue
        hop_no = parts[0]
        if not hop_no.isdigit():
            continue
        host = next((part for part in parts[1:] if part not in {"*", "ms"}), None)
        hops.append({"hop": int(hop_no), "host": None if host == "*" else host, "raw": stripped})
    return hops


async def traceroute(host: str, timeout: float = 18.0) -> Dict[str, Any]:
    validate_host(host)
    command = _traceroute_command(host)
    if command is None:
        return {"ok": False, "hops": [], "error": "Traceroute is not available on this platform"}
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return {"ok": False, "hops": [], "error": "traceroute is not installed"}
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return {"ok": False, "hops": [], "error": "Traceroute timed out"}
    output = stdout.decode(errors="ignore") or stderr.decode(errors="ignore")
    hops = _parse_hops(output)
    return {"ok": bool(hops), "hops": hops, "error": None if hops else (output.strip() or "No hops returned")}


async def run_diagnostics(host: str, include_traceroute: bool = False, kind: str = "other") -> Dict[str, Any]:
    validate_host(host)
    ports = KIND_PORTS.get(kind, KIND_PORTS["other"])
    ping = await ping_host(host, timeout=2.0)
    tcp = await asyncio.gather(*(check_tcp(host, port) for port in ports))
    payload: Dict[str, Any] = {
        "host": host,
        "kind": kind,
        "ping": {"is_up": ping.is_up, "rtt_ms": ping.rtt_ms, "error": ping.error},
        "tcp": list(tcp),
        "traceroute": None,
        "insight": None,
    }
    hops = None
    if include_traceroute:
        payload["traceroute"] = await traceroute(host)
        hops = payload["traceroute"].get("hops") or []
    open_ports = [item["port"] for item in tcp if item.get("open")]
    payload["insight"] = build_insight(
        kind,
        host,
        status="up" if ping.is_up else "down",
        error=ping.error,
        rtt_ms=ping.rtt_ms,
        tcp_open=open_ports,
        traceroute_hops=hops,
    )
    return payload
