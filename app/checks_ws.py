from __future__ import annotations

import asyncio
import base64
import os
import ssl
import time
from typing import Optional

from app.pinger import PingOutcome, validate_host


def _path(value: Optional[str]) -> str:
    path = (value or "/").strip() or "/"
    if not path.startswith("/"):
        path = "/" + path
    return path[:200]


async def check_websocket(
    host: str,
    port: int,
    *,
    path: Optional[str] = None,
    secure: bool = False,
    timeout: float = 2.0,
) -> PingOutcome:
    host = validate_host(host)
    path = _path(path)
    ssl_ctx = None
    server_hostname = None
    if secure:
        ssl_ctx = ssl.create_default_context()
        server_hostname = host
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ssl_ctx, server_hostname=server_hostname),
            timeout=timeout,
        )
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "WebSocket connection failed")
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        "GET %s HTTP/1.1\r\n"
        "Host: %s:%s\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: %s\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    ) % (path, host, port, key)
    try:
        writer.write(request.encode("ascii"))
        await writer.drain()
        header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=timeout)
        first = header.split(b"\r\n", 1)[0].decode("ascii", "ignore")
        rtt = round((time.perf_counter() - started) * 1000.0, 2)
        if " 101 " in first or first.endswith(" 101"):
            return PingOutcome(True, rtt, None)
        return PingOutcome(False, None, "WebSocket handshake failed (%s)" % (first[:80] or "no status"))
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "WebSocket handshake failed")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
