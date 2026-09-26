from datetime import datetime, timedelta, timezone

from app.sslcheck import (
    domain_candidates,
    issuer_label,
    issuer_provider,
    normalize_ssl_host,
    parse_rdap_expiry,
    ssl_applicable,
    ssl_view,
    tls_target,
)


def test_ip_has_no_domain_candidates():
    assert domain_candidates("10.0.0.8") == []
    assert domain_candidates("2001:db8::1") == []
    assert domain_candidates("192.00.98.26") == []


def test_hostname_domain_candidates_walk_to_registrable():
    assert domain_candidates("www.example.com") == ["www.example.com", "example.com"]
    assert domain_candidates("example.com") == ["example.com"]
    assert domain_candidates("*.superstack.in") == ["superstack.in"]


def test_tls_target_for_https_style_monitors():
    assert tls_target("edge.example.com", "tcp", 443) == ("edge.example.com", 443)
    assert tls_target("edge.example.com", "tcp", 22) == ("edge.example.com", 443)
    assert tls_target("chat.example.com", "websocket", 443, {"secure": True}) == ("chat.example.com", 443)
    assert tls_target("www.example.com", "ping", None) == ("www.example.com", 443)
    assert tls_target("10.0.0.8", "ping", None) == ("10.0.0.8", 443)
    assert tls_target("10.0.0.8", "tcp", 443) == ("10.0.0.8", 443)


def test_ssl_applicable_for_domain_or_https():
    assert ssl_applicable("www.example.com", "ping", None)
    assert ssl_applicable("edge.example.com", "tcp", 443)
    assert ssl_applicable("10.0.0.8", "ping", None)
    assert tls_target("db.lab.local", "tcp", 3306) == ("db.lab.local", 443)
    assert ssl_applicable("db.lab.local", "ping", None)


def test_parse_rdap_expiry_reads_registrar_and_date():
    payload = {
        "ldhName": "EXAMPLE.COM",
        "events": [
            {"eventAction": "registration", "eventDate": "1995-08-14T04:00:00Z"},
            {"eventAction": "expiration", "eventDate": "2027-08-13T04:00:00Z"},
        ],
        "entities": [
            {
                "roles": ["registrar"],
                "vcardArray": ["vcard", [["fn", {}, "text", "Example Registrar"]]],
            }
        ],
    }
    parsed = parse_rdap_expiry(payload)
    assert parsed["name"] == "example.com"
    assert parsed["expires_at"] == "2027-08-13T04:00:00Z"
    assert parsed["registered_at"] == "1995-08-14T04:00:00Z"
    assert parsed["registrar"] == "Example Registrar"


def test_ssl_view_computes_days_left_from_stored_certificate():
    future = (datetime.now(timezone.utc) + timedelta(days=40)).replace(microsecond=0)
    raw = (
        '{"cert":{"not_after":"%s","common_name":"www.example.com","issuer":"CN=Test",'
        '"port":443,"checked_at":"2026-09-25T00:00:00Z"},"domain":null}'
        % future.replace(tzinfo=None).isoformat()
    )
    view = ssl_view(raw, "www.example.com", "tcp", 443)
    assert view["applicable"] is True
    assert view["has_tls"] is True
    assert view["has_domain"] is True
    assert view["cert"]["common_name"] == "www.example.com"
    assert view["cert"]["status"] == "Valid"
    assert view["cert"]["days_left"] >= 39
    assert view["cert"]["issuer"] == "Test"
    assert "ssl-logo" in view["cert"]["logo"]


def test_ssl_view_ip_ping_tries_until_checked():
    view = ssl_view(None, "10.0.0.8", "ping", None)
    assert view["applicable"] is True
    assert view["has_tls"] is True
    assert view["has_domain"] is False
    assert view["cert"] is None
    empty = ssl_view('{"cert":null,"domain":null}', "10.0.0.8", "ping", None)
    assert empty["applicable"] is False
    assert empty["has_tls"] is False


def test_ssl_view_ip_uses_certificate_names_for_domain():
    future = (datetime.now(timezone.utc) + timedelta(days=40)).replace(microsecond=0)
    raw = (
        '{"cert":{"not_after":"%s","common_name":"superstack.in","sans":["superstack.in"],'
        '"issuer":"O=Let\'s Encrypt","port":443,"checked_at":"2026-09-25T00:00:00Z"},"domain":null}'
        % future.replace(tzinfo=None).isoformat()
    )
    view = ssl_view(raw, "216.198.79.1", "ping", None)
    assert view["applicable"] is True
    assert view["has_tls"] is True
    assert view["has_domain"] is True
    assert view["cert"]["common_name"] == "superstack.in"


def test_ssl_view_ignores_cdn_catchall_on_ip():
    future = (datetime.now(timezone.utc) + timedelta(days=40)).replace(microsecond=0)
    raw = (
        '{"cert":{"not_after":"%s","common_name":"no-sni.vercel-infra.com",'
        '"sans":["no-sni.vercel-infra.com"],"port":443,"checked_at":"2026-09-25T00:00:00Z"},"domain":null}'
        % future.replace(tzinfo=None).isoformat()
    )
    view = ssl_view(raw, "216.198.79.1", "ping", None)
    assert view["has_tls"] is False
    assert view["cert"] is None


def test_ssl_view_ip_on_tls_port_has_cert_only():
    view = ssl_view(None, "10.0.0.8", "tcp", 443)
    assert view["applicable"] is True
    assert view["has_tls"] is True
    assert view["has_domain"] is False


def test_ssl_view_invalid_when_not_authorized():
    future = (datetime.now(timezone.utc) + timedelta(days=80)).replace(microsecond=0)
    raw = (
        '{"cert":{"not_after":"%s","common_name":"www.example.com","issuer":"O=Entrust Limited",'
        '"authorized":false,"port":443,"checked_at":"2026-09-25T00:00:00Z"},"domain":null}'
        % future.replace(tzinfo=None).isoformat()
    )
    view = ssl_view(raw, "www.example.com", "tcp", 443)
    assert view["cert"]["status"] == "Invalid"
    assert view["cert"]["issuer"] == "Entrust Limited"
    assert view["cert"]["provider"] == "Entrust"
    assert view["cert"]["logo"].endswith("entrust.svg")


def test_issuer_label_prefers_organization():
    assert issuer_label("CN=Entrust OV TLS Issuing RSA CA 1,O=Entrust Limited,C=US") == "Entrust Limited"
    assert issuer_label("CN=Test") == "Test"


def test_issuer_provider_maps_known_cas():
    assert issuer_provider("O=Entrust Limited")["name"] == "Entrust"
    assert issuer_provider("O=Entrust Limited")["logo"].endswith("entrust.svg")
    assert issuer_provider("O=Let's Encrypt")["name"] == "Let's Encrypt"
    assert issuer_provider("O=DigiCert Inc")["name"] == "DigiCert"
    assert issuer_provider("O=Cloudflare, Inc.")["name"] == "Cloudflare"
    assert issuer_provider("O=Sectigo Limited")["name"] == "Sectigo"
    assert issuer_provider("O=Apple Inc.")["name"] == "Apple"
    assert issuer_provider("CN=Apple Public CA, O=Apple Inc., C=US")["logo"].endswith("apple-173-svgrepo-com.svg")
    assert issuer_provider("Apple Inc.")["logo"].endswith("apple-173-svgrepo-com.svg")
    assert issuer_provider("O=Unknown CA")["logo"].endswith("security-protection-ssl-certificate-svgrepo-com.svg")


def test_normalize_ssl_host_strips_urls():
    assert normalize_ssl_host("https://www.Example.com/path") == "www.example.com"
    assert normalize_ssl_host("aep.com:443") == "aep.com"
    try:
        normalize_ssl_host("10.0.0.8")
        assert False, "IP addresses should be rejected"
    except ValueError:
        pass
    try:
        normalize_ssl_host("localhost")
        assert False, "localhost should be rejected"
    except ValueError:
        pass


def test_ssl_report_pdf_includes_pingwatch_branding():
    from app.ssl_report import build_ssl_report_pdf, report_filename

    data = build_ssl_report_pdf(
        {
            "name": "Apple",
            "host": "apple.in",
            "status": "Valid",
            "provider": "Apple",
            "issuer": "Apple Inc.",
            "subject": "apple.in",
            "days_left": 24,
            "not_after": datetime(2026, 10, 19),
            "ssl": {
                "cert": {"serial": "abc123", "sans": ["apple.in"], "common_name": "apple.in"},
                "domain": {"name": "apple.in", "registrar": "Example Registrar", "status": "Valid"},
            },
        },
        {"app_name": "Pingwatch", "company_name": "Acme", "version": "1.2.0"},
    )
    assert data.startswith(b"%PDF")
    assert b"Pingwatch" in data
    assert len(data) > 800
    assert report_filename("apple.in") == "pingwatch-ssl-apple.in.pdf"
    assert report_filename("www.example.com/path") == "pingwatch-ssl-www.example.com-path.pdf"
