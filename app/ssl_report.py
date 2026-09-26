from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

TEAL = HexColor("#145c4c")
TEAL_SOFT = HexColor("#1a6758")
INK = HexColor("#111827")
MUTED = HexColor("#6b7280")
LINE = HexColor("#e6e8ee")
BG = HexColor("#f7f8fb")
VALID = HexColor("#16a34a")
WARN = HexColor("#d97706")
DOWN = HexColor("#e11d48")


def report_filename(host: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", (host or "host").strip()).strip("-._") or "host"
    return "pingwatch-ssl-%s.pdf" % slug[:80]


def _stamp(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y")
    text = str(value).replace("Z", "")
    try:
        return datetime.fromisoformat(text).strftime("%d %b %Y")
    except ValueError:
        return str(value)


def _days(days: Optional[int]) -> str:
    if days is None:
        return "—"
    if days < 0:
        return "%s days ago" % abs(days)
    if days == 0:
        return "Today"
    if days == 1:
        return "1 day"
    return "%s days" % days


def _status_hex(status: str) -> HexColor:
    value = (status or "").strip().lower()
    if value == "valid":
        return VALID
    if value == "expiring":
        return WARN
    if value in {"expired", "invalid"}:
        return DOWN
    return MUTED


def _text(value: Any, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, (list, tuple)):
        joined = ", ".join(str(item) for item in value if item)
        return joined or fallback
    return str(value)


def build_ssl_report_pdf(payload: Dict[str, Any], brand: Dict[str, Any]) -> bytes:
    buffer = BytesIO()
    app_name = brand.get("app_name") or "Pingwatch"
    company = (brand.get("company_name") or "").strip()
    version = brand.get("version") or "1.2.0"
    generated = datetime.utcnow().strftime("%d %b %Y %H:%M UTC")
    name = _text(payload.get("name") or payload.get("host"), "SSL hostname")
    host = _text(payload.get("host"), "")
    status = _text(payload.get("status"), "Unknown")
    ssl = payload.get("ssl") or {}
    cert = ssl.get("cert") or {}
    domain = ssl.get("domain") or {}

    def draw_chrome(canvas, _doc):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(TEAL)
        canvas.rect(0, height - 28 * mm, width, 28 * mm, fill=1, stroke=0)
        canvas.setFillColor(HexColor("#0f766e"))
        canvas.circle(width - 22 * mm, height - 10 * mm, 9 * mm, fill=1, stroke=0)
        canvas.setFillColor(white)
        canvas.setFont("Helvetica-Bold", 17)
        canvas.drawString(18 * mm, height - 13 * mm, app_name)
        canvas.setFont("Helvetica", 9)
        kicker = "SSL certificate report"
        if company:
            kicker = "%s  ·  %s" % (company, kicker)
        canvas.drawString(18 * mm, height - 20.5 * mm, kicker)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(width - 18 * mm, height - 20.5 * mm, "v%s" % version)
        canvas.setFillColor(TEAL_SOFT)
        canvas.rect(0, 0, width, 12 * mm, fill=1, stroke=0)
        canvas.setFillColor(white)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(18 * mm, 5 * mm, "Generated %s" % generated)
        canvas.drawRightString(width - 18 * mm, 5 * mm, "%s  ·  Confidential" % app_name)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=36 * mm,
        bottomMargin=18 * mm,
        title="%s SSL report — %s" % (app_name, host or name),
        author=app_name,
        subject="SSL certificate and domain registration report",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "PwTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=INK,
        spaceAfter=2,
        leading=22,
    )
    lede = ParagraphStyle(
        "PwLede",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=MUTED,
        spaceAfter=12,
        leading=14,
    )
    section = ParagraphStyle(
        "PwSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=TEAL,
        spaceBefore=16,
        spaceAfter=8,
    )
    label = ParagraphStyle(
        "PwLabel",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=MUTED,
        leading=11,
    )
    cell = ParagraphStyle(
        "PwCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        textColor=INK,
        leading=13,
    )
    status_style = ParagraphStyle(
        "PwStatus",
        parent=cell,
        fontName="Helvetica-Bold",
        textColor=_status_hex(status),
    )

    def kv_table(rows):
        data = []
        for key, value, *rest in rows:
            style = rest[0] if rest else cell
            data.append(
                [
                    Paragraph(escape(key), label),
                    value if hasattr(value, "text") else Paragraph(escape(_text(value)), style),
                ]
            )
        table = Table(data, colWidths=[48 * mm, 124 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), BG),
                    ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        return table

    names = cert.get("sans") or []
    if cert.get("common_name") and cert.get("common_name") not in names:
        names = [cert.get("common_name"), *names]

    story = [
        Paragraph(escape(name), title),
        Paragraph(
            escape("https://%s" % host if host else "SSL hostname")
            + ("  ·  Certificate status: <b>%s</b>" % escape(status)),
            lede,
        ),
        Paragraph("Certificate", section),
        kv_table(
            [
                ("Status", Paragraph(escape(status), status_style)),
                ("Issuer / CA", payload.get("provider") or payload.get("issuer") or cert.get("issuer")),
                ("Subject", payload.get("subject") or cert.get("subject") or cert.get("common_name")),
                ("Serial", cert.get("serial")),
                ("Valid from", _stamp(payload.get("not_before") or cert.get("not_before"))),
                ("Valid to", _stamp(payload.get("not_after") or cert.get("not_after"))),
                ("Days remaining", _days(payload.get("days_left") if payload.get("days_left") is not None else cert.get("days_left"))),
                ("Names", ", ".join(str(item) for item in names if item)),
                ("Last checked", _stamp(payload.get("last_checked_at") or cert.get("checked_at"))),
                ("Notes", payload.get("error") or cert.get("error") or "None"),
            ]
        ),
        Paragraph("Domain registration", section),
        kv_table(
            [
                ("Domain", payload.get("domain_name") or domain.get("name") or host),
                ("Status", payload.get("domain_status") or domain.get("status")),
                ("Registrar", domain.get("registrar")),
                ("Registered", _stamp(domain.get("registered_at"))),
                ("Expires", _stamp(payload.get("domain_expires") or domain.get("expires_at"))),
                (
                    "Days remaining",
                    _days(
                        payload.get("domain_days")
                        if payload.get("domain_days") is not None
                        else domain.get("days_left")
                    ),
                ),
                ("Notes", domain.get("error") or "None"),
            ]
        ),
        Spacer(1, 8 * mm),
        Paragraph(
            escape(
                "%s watches the live TLS certificate on port 443 and the public domain registration record. "
                "This PDF is a point-in-time snapshot for operations teams and is not a substitute for a full security audit."
                % app_name
            ),
            lede,
        ),
    ]
    doc.build(story, onFirstPage=draw_chrome, onLaterPages=draw_chrome)
    return buffer.getvalue()
