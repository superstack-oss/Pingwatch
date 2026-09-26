from __future__ import annotations

import asyncio
import ipaddress
import json
import math
import socket
import ssl
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from app.monitors import parse_spec
from app.pinger import validate_host

TLS_PORTS = {443, 8443, 9443, 4443}
CERT_TTL = timedelta(hours=6)
DOMAIN_TTL = timedelta(hours=24)
USER_AGENT = "Pingwatch/1.2.0"
SSL_LOGO_DIR = "/static/public/ssl-logo"
SSL_PROVIDERS = (
    ("apple", "Apple", "apple-173-svgrepo-com.svg", ("apple inc", "apple public ca", "apple certification", "o=apple")),
    ("letsencrypt", "Let's Encrypt", "letsencrypt-svgrepo-com.svg", ("let's encrypt", "letsencrypt", "lets encrypt", "isrg")),
    ("certbot", "Certbot", "certbot-svgrepo-com.svg", ("certbot",)),
    ("cloudflare", "Cloudflare", "cloudflare-svgrepo-com.svg", ("cloudflare",)),
    ("digicert", "DigiCert", "digicert.svg", ("digicert", "rapidssl", "geotrust", "thawte", "encryption everywhere")),
    ("entrust", "Entrust", "entrust.svg", ("entrust", "affirmtrust")),
    ("globalsign", "GlobalSign", "globalsign-main.svg", ("globalsign", "global sign")),
    ("harica", "HARICA", "harica-Logo.svg", ("harica", "hellenic academic")),
    ("sectigo", "Sectigo", "sectigo-logo-new.svg", ("sectigo", "comodo", "positive ssl", "essentialssl", "usertrust", "aaa certificate services")),
    ("zerossl", "ZeroSSL", "zerossl_logo.svg", ("zerossl", "zero ssl")),
    ("actalis", "Actalis", "actalis.svg", ("actalis",)),
    ("openssl", "OpenSSL", "openssl-svgrepo-com.svg", ("openssl", "internet widgits")),
)
DEFAULT_SSL_LOGO = "security-protection-ssl-certificate-svgrepo-com.svg"
DOMAIN_SSL_LOGO = "domain-registration-svgrepo-com.svg"


class SslJob(NamedTuple):
    host: str
    monitor_type: str
    port: Optional[int]
    spec: Dict[str, Any]
    previous: Dict[str, Any]
    force: bool = False
    hints: Tuple[str, ...] = ()


def is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address((host or "").strip("[]"))
        return True
    except ValueError:
        return False


def strip_wildcard(host: str) -> str:
    name = (host or "").strip().strip(".").lower()
    if name.startswith("*."):
        name = name[2:]
    return name


def domain_candidates(host: str) -> List[str]:
    name = strip_wildcard(host)
    if not name or is_ip(name) or "." not in name:
        return []
    labels = [part for part in name.split(".") if part and part != "*"]
    if len(labels) < 2:
        return []
    if all(part.isdigit() for part in labels):
        return []
    return [".".join(labels[index:]) for index in range(0, len(labels) - 1)]


def unique_hostnames(*groups: Any) -> List[str]:
    names: List[str] = []
    for group in groups:
        values: Iterable[Any]
        if group is None:
            continue
        if isinstance(group, (list, tuple, set)):
            values = group
        else:
            values = [group]
        for value in values:
            for name in domain_candidates(str(value or "")):
                if name not in names:
                    names.append(name)
    return names


def reverse_hostnames(host: str) -> List[str]:
    if not is_ip(host):
        return []
    target = (host or "").strip().strip("[]")
    names: List[str] = []
    try:
        name, aliases, _ = socket.gethostbyaddr(target)
    except Exception:
        return []
    for item in [name, *(aliases or ())]:
        if item and item != target and item not in names:
            names.append(item)
    return names


def device_ssl_hints(device: Any) -> Tuple[str, ...]:
    hints: List[str] = []
    name = (getattr(device, "name", None) or "").strip()
    if name:
        hints.append(name)
    notes = (getattr(device, "notes", None) or "").strip()
    if notes:
        for token in notes.replace(",", " ").replace(";", " ").split():
            if domain_candidates(token.strip(" .")):
                hints.append(token.strip(" ."))
    spec = parse_spec(getattr(device, "monitor_spec", None))
    for key in ("hostname", "sni", "server_name", "tls_server_name"):
        value = spec.get(key)
        if value:
            hints.append(str(value).strip())
    return tuple(item for item in hints if item)


def hostnames_for_ip(ip: str, candidates: Sequence[str]) -> Tuple[str, ...]:
    if not is_ip(ip):
        return ()
    target = ip.strip().strip("[]")
    matched: List[str] = []
    for name in unique_hostnames(*candidates):
        try:
            infos = socket.getaddrinfo(name, None)
        except Exception:
            continue
        addresses = {item[4][0] for item in infos}
        if target in addresses and name not in matched:
            matched.append(name)
    return tuple(matched)


async def hostname_peer_hints(session: Any, ip: str) -> Tuple[str, ...]:
    if not is_ip(ip) or session is None:
        return ()
    from sqlalchemy import select

    from app.models import Device, SslHost

    device_hosts = (await session.execute(select(Device.host))).scalars().all()
    ssl_hosts = (await session.execute(select(SslHost.host))).scalars().all()
    candidates = unique_hostnames(*(device_hosts or []), *(ssl_hosts or []))
    if not candidates:
        return ()
    return await asyncio.to_thread(hostnames_for_ip, ip, candidates)


def tls_target(
    host: str, monitor_type: str, port: Optional[int], spec: Optional[Dict[str, Any]] = None
) -> Optional[Tuple[str, int]]:
    spec = spec or {}
    name = (host or "").strip()
    if not name:
        return None
    kind = (monitor_type or "ping").strip().lower()
    if kind == "websocket" and spec.get("secure"):
        return name, int(port or 443)
    if port in TLS_PORTS:
        return name, int(port)
    return name, 443


def ssl_applicable(
    host: str,
    monitor_type: str,
    port: Optional[int],
    spec: Optional[Dict[str, Any]] = None,
    hints: Optional[Sequence[str]] = None,
) -> bool:
    return bool(tls_target(host, monitor_type, port, spec) or unique_hostnames(host, hints or ()))


def normalize_ssl_host(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError("Enter a hostname such as example.com")
    if "://" in text:
        parsed = urlparse(text)
        text = parsed.hostname or ""
    else:
        text = text.split("/")[0].split("?")[0].strip()
        if text.startswith("[") and "]" in text:
            text = text[1 : text.index("]")]
        elif ":" in text:
            host_part, port_part = text.rsplit(":", 1)
            if port_part.isdigit():
                text = host_part
    text = text.strip().strip(".").lower()
    host = validate_host(text)
    if is_ip(host) or not domain_candidates(host):
        raise ValueError("Enter a hostname such as example.com")
    return host


def issuer_provider(issuer: Optional[str]) -> Dict[str, str]:
    blob = (issuer or "").lower()
    for key, label, filename, needles in SSL_PROVIDERS:
        if any(needle in blob for needle in needles):
            return {"key": key, "name": label, "logo": "%s/%s" % (SSL_LOGO_DIR, filename)}
    return {
        "key": "generic",
        "name": issuer_label(issuer) or "Certificate",
        "logo": "%s/%s" % (SSL_LOGO_DIR, DEFAULT_SSL_LOGO),
    }


def parse_ssl_info(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("Z", "")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value.replace(microsecond=0).isoformat() + "Z"


def _days_left(value: Optional[datetime], now: Optional[datetime] = None) -> Optional[int]:
    if value is None:
        return None
    stamp = now or datetime.utcnow()
    delta = value.replace(tzinfo=None) - stamp.replace(tzinfo=None)
    return int(math.ceil(delta.total_seconds() / 86400.0))


def _stale(checked_at: Optional[str], ttl: timedelta, now: datetime, force: bool) -> bool:
    if force:
        return True
    parsed = _parse_iso(checked_at)
    if parsed is None:
        return True
    return now - parsed >= ttl


def _cert_datetime(cert: x509.Certificate, attr: str) -> datetime:
    value = getattr(cert, attr + "_utc", None)
    if value is not None:
        return value.replace(tzinfo=None)
    naive = getattr(cert, attr)
    return naive.replace(tzinfo=None) if getattr(naive, "tzinfo", None) else naive


def _read_peer_certificate(host: str, port: int, timeout: float, server_hostname: Optional[str]) -> Dict[str, Any]:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    wrap_kwargs = {"server_hostname": server_hostname} if server_hostname else {}
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with context.wrap_socket(sock, **wrap_kwargs) as tls:
            der = tls.getpeercert(binary_form=True)
    if not der:
        raise ValueError("Server did not present a certificate")
    cert = x509.load_der_x509_certificate(der, default_backend())
    sans: List[str] = []
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        sans = ext.value.get_values_for_type(x509.DNSName)
    except Exception:
        pass
    issuer = cert.issuer.rfc4514_string()
    subject = cert.subject.rfc4514_string()
    cn = None
    try:
        cn = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
    except Exception:
        pass
    authorized = False
    try:
        verify = ssl.create_default_context()
        verify_kwargs = {"server_hostname": server_hostname} if server_hostname else {}
        with socket.create_connection((host, port), timeout=min(timeout, 4.0)) as probe:
            with verify.wrap_socket(probe, **verify_kwargs):
                authorized = True
    except Exception:
        authorized = False
    return {
        "not_before": _iso(_cert_datetime(cert, "not_valid_before")),
        "not_after": _iso(_cert_datetime(cert, "not_valid_after")),
        "issuer": issuer,
        "subject": subject,
        "common_name": cn or (sans[0] if sans else host),
        "sans": sans[:12],
        "serial": format(cert.serial_number, "X"),
        "authorized": authorized,
        "port": port,
        "error": None,
        "checked_at": _iso(datetime.utcnow()),
    }


def fetch_presented_certificate(
    host: str,
    port: int,
    timeout: float = 6.0,
    server_hostname: Optional[str] = None,
    sni_names: Optional[Sequence[Optional[str]]] = None,
) -> Dict[str, Any]:
    named: List[str] = []
    for name in [server_hostname, *(sni_names or ()), None if is_ip(host) else host]:
        if not name or name in named or is_ip(str(name)):
            continue
        named.append(name)
    attempts: List[Optional[str]] = []
    if named:
        attempts.append(named[0])
    if is_ip(host) or not attempts:
        attempts.append(None)
    last_error: Optional[BaseException] = None
    for sni in attempts:
        try:
            return _read_peer_certificate(host, port, timeout, sni)
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise ValueError("Server did not present a certificate")


def parse_rdap_expiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    expires = None
    registered = None
    for event in payload.get("events") or []:
        action = str(event.get("eventAction") or "").lower()
        if action in {"expiration", "expiry"} and not expires:
            expires = event.get("eventDate")
        elif action == "registration" and not registered:
            registered = event.get("eventDate")
    registrar = None
    for entity in payload.get("entities") or []:
        roles = [str(role).lower() for role in (entity.get("roles") or [])]
        if "registrar" not in roles:
            continue
        vcard = entity.get("vcardArray")
        if isinstance(vcard, list) and len(vcard) > 1 and isinstance(vcard[1], list):
            for item in vcard[1]:
                if isinstance(item, list) and item and item[0] == "fn" and len(item) >= 4:
                    registrar = str(item[3])
                    break
        if not registrar:
            registrar = entity.get("handle")
        if registrar:
            break
    name = payload.get("ldhName") or payload.get("unicodeName")
    return {
        "name": str(name).lower() if name else None,
        "expires_at": _iso(_parse_iso(expires)) if expires else None,
        "registered_at": _iso(_parse_iso(registered)) if registered else None,
        "registrar": registrar,
        "error": None,
        "checked_at": _iso(datetime.utcnow()),
    }


def fetch_rdap(domain: str, timeout: float = 8.0) -> Dict[str, Any]:
    url = "https://rdap.org/domain/%s" % domain
    req = Request(
        url,
        headers={
            "Accept": "application/rdap+json, application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except HTTPError as exc:
        raise ValueError("RDAP HTTP %s" % exc.code) from exc
    except URLError as exc:
        raise ValueError(str(exc.reason or exc)) from exc
    if not isinstance(payload, dict):
        raise ValueError("Unexpected RDAP response")
    return parse_rdap_expiry(payload)


def _is_catchall_cert(cert_raw: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(cert_raw, dict):
        return False
    blob = " ".join([str(cert_raw.get("common_name") or ""), " ".join(cert_raw.get("sans") or [])]).lower()
    return "no-sni." in blob or "vercel-infra.com" in blob


def _cert_is_useful(cert_raw: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(cert_raw, dict):
        return False
    if _is_catchall_cert(cert_raw):
        return False
    return bool(cert_raw.get("not_after") or cert_raw.get("common_name") or cert_raw.get("sans"))


def collect_ssl_info(job: SslJob) -> Dict[str, Any]:
    now = datetime.utcnow()
    previous = job.previous or {}
    cert = dict(previous.get("cert") or {}) if previous.get("cert") else None
    domain = dict(previous.get("domain") or {}) if previous.get("domain") else None
    hints = unique_hostnames(job.host, job.hints, reverse_hostnames(job.host))
    target = tls_target(job.host, job.monitor_type, job.port, job.spec)
    if target:
        if _stale((cert or {}).get("checked_at"), CERT_TTL, now, job.force):
            host, port = target
            try:
                cert = fetch_presented_certificate(host, port, sni_names=hints)
                if is_ip(job.host) and _is_catchall_cert(cert):
                    cert = None
            except Exception as exc:
                if _cert_is_useful(cert) or unique_hostnames(job.host, job.hints):
                    cert = {
                        "not_after": (cert or {}).get("not_after"),
                        "not_before": (cert or {}).get("not_before"),
                        "issuer": (cert or {}).get("issuer"),
                        "subject": (cert or {}).get("subject"),
                        "common_name": (cert or {}).get("common_name"),
                        "sans": (cert or {}).get("sans") or [],
                        "serial": (cert or {}).get("serial"),
                        "authorized": False,
                        "port": port,
                        "error": str(exc),
                        "checked_at": _iso(now),
                    }
                else:
                    cert = None
    else:
        cert = None
    names = unique_hostnames(job.host, job.hints, reverse_hostnames(job.host), (cert or {}).get("common_name"), (cert or {}).get("sans"))
    if names:
        if _stale((domain or {}).get("checked_at"), DOMAIN_TTL, now, job.force):
            last_error = None
            found = None
            for name in names:
                try:
                    found = fetch_rdap(name)
                    found["name"] = found.get("name") or name
                    break
                except Exception as exc:
                    last_error = str(exc)
            domain = found or {
                "name": names[-1],
                "expires_at": (domain or {}).get("expires_at"),
                "registered_at": (domain or {}).get("registered_at"),
                "registrar": (domain or {}).get("registrar"),
                "error": last_error or "Domain registration lookup failed",
                "checked_at": _iso(now),
            }
    else:
        domain = None
    return {"cert": cert, "domain": domain}


def issuer_label(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip()
    if not text or "=" not in text:
        return text or None
    parts: Dict[str, str] = {}
    for chunk in text.split(","):
        if "=" not in chunk:
            continue
        key, raw = chunk.split("=", 1)
        parts[key.strip().upper()] = raw.strip()
    return parts.get("O") or parts.get("CN") or text


def expiry_status(days: Optional[int], error: Optional[str]) -> Optional[str]:
    if error:
        return "Invalid"
    if days is None:
        return None
    if days < 0:
        return "Expired"
    if days <= 30:
        return "Expiring"
    return "Valid"


def ssl_view(
    raw: Optional[str],
    host: str,
    monitor_type: str,
    port: Optional[int],
    spec: Optional[Dict[str, Any]] = None,
    hints: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    info = parse_ssl_info(raw)
    now = datetime.utcnow()
    cert_raw = info.get("cert") if isinstance(info.get("cert"), dict) else None
    domain_raw = info.get("domain") if isinstance(info.get("domain"), dict) else None
    hostname_like = bool(unique_hostnames(host, hints or ()))
    names = unique_hostnames(host, hints or (), (cert_raw or {}).get("common_name"), (cert_raw or {}).get("sans"))
    useful_cert = _cert_is_useful(cert_raw)
    useful_domain = bool(domain_raw and (domain_raw.get("name") or domain_raw.get("expires_at") or domain_raw.get("error")))
    checked = bool(info)
    applicable = hostname_like or useful_cert or useful_domain or not checked
    has_tls = bool(tls_target(host, monitor_type, port, spec)) and (hostname_like or useful_cert or not checked)
    has_domain = bool(names or useful_domain)
    cert = None
    if cert_raw and (useful_cert or hostname_like):
        not_after = _parse_iso(cert_raw.get("not_after"))
        days = _days_left(not_after, now)
        authorized = cert_raw.get("authorized")
        error = cert_raw.get("error")
        if error or authorized is False:
            status = "Invalid"
        else:
            status = expiry_status(days, None)
        labeled = issuer_label(cert_raw.get("issuer")) or cert_raw.get("issuer")
        provider = issuer_provider(cert_raw.get("issuer") or labeled)
        cert = {
            "not_after": not_after,
            "not_before": _parse_iso(cert_raw.get("not_before")),
            "issuer": labeled,
            "provider": provider["name"],
            "logo": provider["logo"],
            "subject": cert_raw.get("common_name") or cert_raw.get("subject"),
            "common_name": cert_raw.get("common_name"),
            "sans": cert_raw.get("sans") or [],
            "serial": cert_raw.get("serial"),
            "port": cert_raw.get("port"),
            "days_left": days,
            "status": status,
            "authorized": authorized,
            "checked_at": _parse_iso(cert_raw.get("checked_at")),
            "error": error,
        }
    domain = None
    if domain_raw:
        expires = _parse_iso(domain_raw.get("expires_at"))
        days = _days_left(expires, now)
        domain = {
            "name": domain_raw.get("name"),
            "expires_at": expires,
            "registered_at": _parse_iso(domain_raw.get("registered_at")),
            "registrar": domain_raw.get("registrar"),
            "days_left": days,
            "status": expiry_status(days, domain_raw.get("error")),
            "checked_at": _parse_iso(domain_raw.get("checked_at")),
            "error": domain_raw.get("error"),
        }
    return {
        "applicable": applicable,
        "has_tls": has_tls,
        "has_domain": has_domain,
        "host": host,
        "cert": cert,
        "domain": domain,
    }


def ssl_view_for_device(device: Any) -> Dict[str, Any]:
    spec = parse_spec(getattr(device, "monitor_spec", None))
    return ssl_view(
        getattr(device, "ssl_info", None),
        device.host,
        getattr(device, "monitor_type", None) or "ping",
        getattr(device, "port", None),
        spec,
        hints=device_ssl_hints(device),
    )


async def refresh_device_ssl(device: Any, force: bool = False, session: Any = None) -> Dict[str, Any]:
    hints = list(device_ssl_hints(device))
    if is_ip(device.host):
        hints.extend(await hostname_peer_hints(session, device.host))
    spec = parse_spec(getattr(device, "monitor_spec", None))
    job = SslJob(
        host=device.host,
        monitor_type=getattr(device, "monitor_type", None) or "ping",
        port=getattr(device, "port", None),
        spec=spec,
        previous=parse_ssl_info(getattr(device, "ssl_info", None)),
        force=force,
        hints=tuple(dict.fromkeys(hints)),
    )
    if not ssl_applicable(job.host, job.monitor_type, job.port, job.spec, hints) and not job.previous:
        return {}
    info = await asyncio.to_thread(collect_ssl_info, job)
    device.ssl_info = json.dumps(info)
    return info


async def refresh_ssl_host(row: Any, force: bool = False) -> Dict[str, Any]:
    job = SslJob(
        host=row.host,
        monitor_type="ping",
        port=None,
        spec={},
        previous=parse_ssl_info(getattr(row, "ssl_info", None)),
        force=force,
    )
    info = await asyncio.to_thread(collect_ssl_info, job)
    row.ssl_info = json.dumps(info)
    row.last_checked_at = datetime.utcnow()
    return info


def ssl_host_payload(row: Any) -> Dict[str, Any]:
    view = ssl_view(getattr(row, "ssl_info", None), row.host, "ping", None)
    cert = view.get("cert") or {}
    domain = view.get("domain") or {}
    generic = issuer_provider(cert.get("issuer"))
    status = cert.get("status") or ("Invalid" if cert.get("error") else "Unknown")
    return {
        "id": row.id,
        "name": row.name,
        "host": row.host,
        "status": status,
        "issuer": cert.get("issuer"),
        "provider": cert.get("provider") or generic["name"],
        "logo": cert.get("logo") or generic["logo"],
        "subject": cert.get("subject") or cert.get("common_name"),
        "days_left": cert.get("days_left"),
        "not_after": cert.get("not_after"),
        "not_before": cert.get("not_before"),
        "domain_name": domain.get("name"),
        "domain_expires": domain.get("expires_at"),
        "domain_days": domain.get("days_left"),
        "domain_status": domain.get("status"),
        "last_checked_at": getattr(row, "last_checked_at", None) or cert.get("checked_at"),
        "error": cert.get("error") or domain.get("error"),
        "ssl": view,
    }
