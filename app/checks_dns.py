from __future__ import annotations

import asyncio
import time
from typing import Optional

from app.pinger import PingOutcome, is_ip_address, validate_host

DNS_TYPES = ("A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR")


def _normalize_qtype(value: Optional[str]) -> str:
    qtype = (value or "A").strip().upper()
    if qtype not in DNS_TYPES:
        raise ValueError("DNS record type must be one of %s" % ", ".join(DNS_TYPES))
    return qtype


async def query_resolver(
    name: str,
    qtype: str = "A",
    nameserver: Optional[str] = None,
    timeout: float = 2.0,
) -> PingOutcome:
    """Look up `name` against a chosen resolver (or the system resolver)."""
    name = validate_host(name)
    qtype = _normalize_qtype(qtype)
    resolver_ip = None
    if nameserver:
        resolver_ip = validate_host(nameserver)
        if not is_ip_address(resolver_ip):
            raise ValueError("DNS resolver must be an IP address")
    try:
        import dns.asyncresolver
        import dns.exception
        import dns.resolver
    except ImportError:
        if resolver_ip:
            return PingOutcome(False, None, "dnspython is required for a custom DNS resolver")
        return await _system_lookup(name, qtype, timeout)

    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = timeout
    resolver.timeout = timeout
    if resolver_ip:
        resolver.nameservers = [resolver_ip]
        resolver.port = 53
    started = time.perf_counter()
    try:
        answer = await resolver.resolve(name, qtype)
        rtt = round((time.perf_counter() - started) * 1000.0, 2)
        if not answer:
            return PingOutcome(False, None, "No %s records for %s" % (qtype, name))
        return PingOutcome(True, rtt, None)
    except dns.resolver.NXDOMAIN:
        return PingOutcome(False, None, "NXDOMAIN for %s" % name)
    except dns.resolver.NoAnswer:
        return PingOutcome(False, None, "No %s records for %s" % (qtype, name))
    except dns.resolver.NoNameservers:
        return PingOutcome(False, None, "Resolver %s refused or is unreachable" % (resolver_ip or "system"))
    except (dns.exception.Timeout, asyncio.TimeoutError):
        return PingOutcome(False, None, "DNS timeout")
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "DNS lookup failed")


async def _system_lookup(name: str, qtype: str, timeout: float) -> PingOutcome:
    if qtype not in {"A", "AAAA"}:
        return PingOutcome(False, None, "Install dnspython to look up %s records" % qtype)
    loop = asyncio.get_running_loop()
    family = 0
    try:
        import socket

        family = socket.AF_INET6 if qtype == "AAAA" else socket.AF_INET
        started = time.perf_counter()
        infos = await asyncio.wait_for(loop.getaddrinfo(name, None, family=family), timeout=timeout)
        rtt = round((time.perf_counter() - started) * 1000.0, 2)
        if not infos:
            return PingOutcome(False, None, "No %s records for %s" % (qtype, name))
        return PingOutcome(True, rtt, None)
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "DNS lookup failed")
