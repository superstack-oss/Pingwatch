from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AppSetting, AuditLog, User

DEFAULTS = {
    "timezone": "UTC",
    "notify_on_down": "false",
    "notify_on_access_request": "true",
    "notify_email": "",
    "notify_downtime_only": "true",
    "servicenow_enabled": "false",
    "servicenow_url": "",
    "servicenow_user": "",
    "servicenow_password": "",
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from": "",
    "smtp_tls": "true",
    "email_domain_restriction": "",
    "ping_interval": str(settings.ping_interval),
    "incidents_enabled": "true",
    "company_name": "",
}

PING_INTERVAL_CHOICES = (
    [1, 5, 10, 20, 30, 60, 300, 900, 1800]
    + [3600 * hour for hour in range(1, 13)]
    + [48 * 3600, 72 * 3600]
)


COMPANY_NAME_MAX = 15


def clean_company_name(value: Any) -> str:
    text = " ".join(str(value or "").split())
    return text[:COMPANY_NAME_MAX]


def setting_flag(raw: Optional[Dict[str, str]], key: str, default: bool = True) -> bool:
    payload = raw or {}
    if key not in payload or payload.get(key) in (None, ""):
        return default
    return str(payload.get(key)).lower() in {"1", "true", "yes", "on"}


def clamp_ping_interval(value: Any, fallback: Optional[int] = None) -> int:
    allowed = PING_INTERVAL_CHOICES
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(fallback if fallback is not None else settings.ping_interval)
    if number in allowed:
        return number
    return min(allowed, key=lambda item: abs(item - number))


async def get_setting(db: AsyncSession, key: str, default: Optional[str] = None) -> str:
    row = await db.get(AppSetting, key)
    if row is None:
        return DEFAULTS.get(key, default or "")
    return row.value


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value


async def all_settings(db: AsyncSession) -> Dict[str, str]:
    rows = (await db.execute(select(AppSetting))).scalars().all()
    payload = dict(DEFAULTS)
    for row in rows:
        payload[row.key] = row.value
    return payload


async def seed_settings(db: AsyncSession) -> None:
    for key, value in DEFAULTS.items():
        existing = await db.get(AppSetting, key)
        if existing is None:
            db.add(AppSetting(key=key, value=value))
    await db.commit()


def public_settings(raw: Dict[str, str]) -> Dict[str, Any]:
    return {
        "timezone": raw.get("timezone") or "UTC",
        "ping_interval": clamp_ping_interval(raw.get("ping_interval")),
        "incidents_enabled": setting_flag(raw, "incidents_enabled", True),
        "company_name": clean_company_name(raw.get("company_name")),
        "app_name": "Pingwatch",
        "version": "1.2.0",
    }


async def write_audit(
    db: AsyncSession,
    action: str,
    detail: str = "",
    user: Optional[User] = None,
    request: Optional[Request] = None,
) -> None:
    ip = None
    if request is not None:
        ip = request.client.host if request.client else None
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            actor=user.username if user else "system",
            action=action,
            detail=detail,
            ip_address=ip,
            created_at=datetime.utcnow(),
        )
    )
