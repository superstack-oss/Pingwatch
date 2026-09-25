from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Dict, Optional

from app.settings_store import all_settings


def _enabled(value: str) -> bool:
    return str(value).lower() in {"1", "true", "yes", "on"}


def send_mail(config: Dict[str, str], to_addr: str, subject: str, body: str) -> Optional[str]:
    host = (config.get("smtp_host") or "").strip()
    if not host:
        return "SMTP is not configured"
    try:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = config.get("smtp_from") or config.get("smtp_user") or "pingwatch@localhost"
        message["To"] = to_addr
        message.set_content(body)
        port = int(config.get("smtp_port") or 587)
        if _enabled(config.get("smtp_tls") or "true"):
            server = smtplib.SMTP(host, port, timeout=8)
            server.starttls()
        else:
            server = smtplib.SMTP(host, port, timeout=8)
        user = config.get("smtp_user") or ""
        if user:
            server.login(user, config.get("smtp_password") or "")
        server.send_message(message)
        server.quit()
        return None
    except Exception as exc:
        return str(exc)


async def notify(db, to_addr: str, subject: str, body: str) -> Optional[str]:
    config = await all_settings(db)
    return send_mail(config, to_addr, subject, body)
