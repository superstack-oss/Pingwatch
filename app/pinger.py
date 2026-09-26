from __future__ import annotations

import asyncio
import ipaddress
import platform
import re
from typing import List, NamedTuple, Optional

from app.insight import classify_from_output

HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)
RTT_RE = re.compile(r"time[=<]([\d.]+)\s*ms", re.IGNORECASE)


class PingOutcome(NamedTuple):
    is_up: bool
    rtt_ms: Optional[float]
    error: Optional[str]
    resolved_ip: Optional[str] = None
    addresses: tuple = ()


def validate_host(value: str) -> str:
    host = value.strip().lower()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if not host or len(host) > 253:
        raise ValueError("Enter a hostname or IP address")
    if any(ch.isspace() for ch in host) or any(ch in host for ch in ";|&$`\\\"'<>"):
        raise ValueError("Enter a hostname or IP address")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if HOSTNAME_RE.fullmatch(host):
        return host
    raise ValueError("Enter a valid hostname or IP address")


def is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _ping_command(host: str, timeout: float) -> List[str]:
    system = platform.system()
    if system == "Darwin":
        return ["ping", "-c", "1", "-W", str(max(1, int(timeout * 1000))), host]
    if system == "Windows":
        return ["ping", "-n", "1", "-w", str(max(1, int(timeout * 1000))), host]
    cmd = ["ping", "-c", "1", "-W", str(max(1, int(round(timeout)))), host]
    if is_ip_address(host) and ":" not in host.strip("[]"):
        cmd.insert(1, "-4")
    return cmd


def classify_ping_error(output: str, returncode: Optional[int]) -> str:
    return classify_from_output(output, returncode)


async def ping_host(host: str, timeout: float) -> PingOutcome:
    validate_host(host)
    proc = await asyncio.create_subprocess_exec(
        *_ping_command(host, timeout),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout + 1.5)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return PingOutcome(False, None, "Request timeout")
    output = stdout.decode(errors="ignore") + stderr.decode(errors="ignore")
    if proc.returncode != 0:
        return PingOutcome(False, None, classify_ping_error(output, proc.returncode))
    match = RTT_RE.search(output)
    return PingOutcome(True, float(match.group(1)) if match else None, None)
