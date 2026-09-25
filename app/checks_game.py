from __future__ import annotations

import asyncio
import json
import socket
import struct
import time
from app.game_types import game_info
from app.pinger import PingOutcome, is_ip_address, validate_host

A2S_INFO = b"\xff\xff\xff\xffTSource Engine Query\x00"
GAMESPY_INFO = b"\\info\\"
QUAKE3_STATUS = b"\xff\xff\xff\xffgetstatus\n"
MUMBLE_PING = b"\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08"
BEDROCK_MAGIC = bytes.fromhex("00ffff00fefefefefdfdfdfd12345678")


async def udp_exchange(host: str, port: int, payload: bytes, timeout: float) -> bytes:
    loop = asyncio.get_running_loop()
    received: asyncio.Future = loop.create_future()

    class _Proto(asyncio.DatagramProtocol):
        def datagram_received(self, data, _addr):
            if not received.done():
                received.set_result(data)

        def error_received(self, exc):
            if not received.done():
                received.set_exception(exc)

    transport, _protocol = await loop.create_datagram_endpoint(_Proto, remote_addr=(host, port))
    try:
        transport.sendto(payload)
        return await asyncio.wait_for(received, timeout=timeout)
    finally:
        transport.close()


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | 0x80 if value else byte)
        if not value:
            return bytes(out)


def _mc_string(text: str) -> bytes:
    data = text.encode("utf-8")
    return _varint(len(data)) + data


async def _read_varint(reader: asyncio.StreamReader) -> int:
    value = 0
    shift = 0
    for _ in range(5):
        byte = await reader.readexactly(1)
        value |= (byte[0] & 0x7F) << shift
        if byte[0] & 0x80 == 0:
            return value
        shift += 7
    raise ValueError("Invalid Minecraft varint")


async def check_a2s(host: str, port: int, timeout: float) -> PingOutcome:
    started = time.perf_counter()
    try:
        data = await udp_exchange(host, port, A2S_INFO, timeout)
        if len(data) >= 9 and data[4] == 0x41:
            data = await udp_exchange(host, port, A2S_INFO + data[5:9], timeout)
        if len(data) > 4 and data[4] in {0x49, 0x6D}:
            return PingOutcome(True, round((time.perf_counter() - started) * 1000.0, 2), None)
        return PingOutcome(False, None, "Game server did not answer an A2S query")
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "A2S query failed")


async def check_gamespy(host: str, port: int, timeout: float) -> PingOutcome:
    started = time.perf_counter()
    try:
        data = await udp_exchange(host, port, GAMESPY_INFO, timeout)
        if b"\\" in data:
            return PingOutcome(True, round((time.perf_counter() - started) * 1000.0, 2), None)
        return PingOutcome(False, None, "Game server did not answer a GameSpy query")
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "GameSpy query failed")


async def check_quake3(host: str, port: int, timeout: float) -> PingOutcome:
    started = time.perf_counter()
    try:
        data = await udp_exchange(host, port, QUAKE3_STATUS, timeout)
        if b"statusResponse" in data or b"infoResponse" in data:
            return PingOutcome(True, round((time.perf_counter() - started) * 1000.0, 2), None)
        return PingOutcome(False, None, "Game server did not answer a Quake 3 query")
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "Quake 3 query failed")


async def check_factorio(host: str, port: int, timeout: float) -> PingOutcome:
    started = time.perf_counter()
    try:
        data = await udp_exchange(host, port, b"\x00", timeout)
        if data:
            return PingOutcome(True, round((time.perf_counter() - started) * 1000.0, 2), None)
        return PingOutcome(False, None, "Factorio server did not answer")
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "Factorio query failed")


async def check_samp(host: str, port: int, timeout: float) -> PingOutcome:
    ip = socket.inet_aton(host) if is_ip_address(host) else b"\x00\x00\x00\x00"
    packet = b"SAMP" + ip + struct.pack("<H", port) + b"i"
    started = time.perf_counter()
    try:
        data = await udp_exchange(host, port, packet, timeout)
        if data.startswith(b"SAMP"):
            return PingOutcome(True, round((time.perf_counter() - started) * 1000.0, 2), None)
        return PingOutcome(False, None, "SA-MP server did not answer")
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "SA-MP query failed")


async def check_mumble(host: str, port: int, timeout: float) -> PingOutcome:
    started = time.perf_counter()
    try:
        data = await udp_exchange(host, port, MUMBLE_PING, timeout)
        if len(data) >= 24:
            return PingOutcome(True, round((time.perf_counter() - started) * 1000.0, 2), None)
        return PingOutcome(False, None, "Mumble server did not answer")
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "Mumble query failed")


async def check_bedrock(host: str, port: int, timeout: float) -> PingOutcome:
    packet = b"\x01" + struct.pack(">Q", int(time.time() * 1000)) + BEDROCK_MAGIC + struct.pack(">Q", 0)
    started = time.perf_counter()
    try:
        data = await udp_exchange(host, port, packet, timeout)
        if data[:1] == b"\x1c":
            return PingOutcome(True, round((time.perf_counter() - started) * 1000.0, 2), None)
        return PingOutcome(False, None, "Bedrock server did not answer")
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "Bedrock query failed")


async def check_fivem(host: str, port: int, timeout: float) -> PingOutcome:
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        writer.write(("GET /info.json HTTP/1.0\r\nHost: %s\r\n\r\n" % host).encode("ascii"))
        await writer.drain()
        body = await asyncio.wait_for(reader.read(4096), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        text = body.decode("utf-8", "ignore")
        payload = text.split("\r\n\r\n", 1)[-1]
        data = json.loads(payload)
        if isinstance(data, dict):
            return PingOutcome(True, round((time.perf_counter() - started) * 1000.0, 2), None)
        return PingOutcome(False, None, "FiveM info.json was not an object")
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "FiveM query failed")


async def check_minecraft(host: str, port: int, timeout: float) -> PingOutcome:
    handshake = _varint(0) + _varint(760) + _mc_string(host) + struct.pack(">H", port) + _varint(1)
    packet = _varint(len(handshake)) + handshake + _varint(1) + _varint(0)
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        writer.write(packet)
        await writer.drain()
        length = await asyncio.wait_for(_read_varint(reader), timeout=timeout)
        payload = await asyncio.wait_for(reader.readexactly(length), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        # packet id + string length + json
        if b"{" in payload:
            json.loads(payload[payload.find(b"{") :].decode("utf-8", "ignore"))
            return PingOutcome(True, round((time.perf_counter() - started) * 1000.0, 2), None)
        return PingOutcome(False, None, "Minecraft server did not return status JSON")
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "Minecraft query failed")


_PROTOCOL = {
    "a2s": check_a2s,
    "gamespy4": check_gamespy,
    "quake3": check_quake3,
    "factorio": check_factorio,
    "samp": check_samp,
    "mumble": check_mumble,
    "bedrock": check_bedrock,
    "fivem": check_fivem,
    "minecraft": check_minecraft,
}


async def check_game(
    host: str,
    port: int,
    game_type: str,
    timeout: float = 2.0,
) -> PingOutcome:
    host = validate_host(host)
    info = game_info(game_type)
    if not info:
        return PingOutcome(False, None, "Unknown game type")
    _label, protocol, _default_port = info
    probe = _PROTOCOL.get(protocol)
    if not probe:
        return PingOutcome(False, None, "No native query for %s" % game_type)
    return await probe(host, port, timeout)
