from __future__ import annotations

import asyncio
import socket
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from app.config import settings
from app.pinger import is_ip_address, validate_host

_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


async def lookup_dns(host: str, force: bool = False) -> Dict[str, Any]:
    host = validate_host(host)
    now = time.time()
    cached = _cache.get(host)
    if cached and not force and cached[0] > now:
        return cached[1]

    payload: Dict[str, Any] = {
        "host": host,
        "is_ip": is_ip_address(host),
        "ok": False,
        "addresses": [],
        "reverse": [],
        "elapsed_ms": None,
        "error": None,
        "checked_at": datetime.utcnow(),
    }
    loop = asyncio.get_running_loop()
    started = time.perf_counter()
    try:
        infos = await asyncio.wait_for(loop.getaddrinfo(host, None), timeout=3.0)
        addresses = sorted({item[4][0] for item in infos})
        payload["addresses"] = addresses
        payload["ok"] = True
        reverse = []
        for address in addresses[:6]:
            try:
                name, _aliases, _ = await asyncio.wait_for(
                    loop.getnameinfo((address, 0), socket.NI_NAMEREQD), timeout=2.0
                )
                if name and name not in reverse:
                    reverse.append(name)
            except Exception:
                try:
                    name, _, _ = await asyncio.wait_for(loop.getnameinfo((address, 0), 0), timeout=2.0)
                    if name and name != address and name not in reverse:
                        reverse.append(name)
                except Exception:
                    continue
        payload["reverse"] = reverse
    except Exception as exc:
        payload["error"] = str(exc) or "DNS lookup failed"
        payload["ok"] = False
    payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
    _cache[host] = (now + settings.dns_cache_ttl, payload)
    return payload
