from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import AccessRequest, AuditLog, Device, User
from app.monitors import apply_monitor_fields
from app.queries import RANGE_DELTA, TABLE_PAGE_SIZE, page_bounds, recent_by_device, stats_since, to_device_out
from app.schemas import DeviceOut, DeviceUpdate, UserOut
from app.security import require_admin
from app.notifiers import CHANNELS, test_channel
from app.servicenow import test_connection
from app.settings_store import (
    MASKED_SECRET,
    all_settings,
    clamp_ping_interval,
    clean_company_name,
    redact_settings,
    set_setting,
    write_audit,
)

router = APIRouter()

EDITABLE_SETTINGS = [
    "timezone",
    "notify_on_down",
    "notify_on_access_request",
    "notify_email",
    "notify_downtime_only",
    "notify_teams_enabled",
    "notify_teams_webhook",
    "notify_slack_enabled",
    "notify_slack_webhook",
    "notify_webhook_enabled",
    "notify_webhook_url",
    "notify_webhook_secret",
    "notify_pagerduty_enabled",
    "notify_pagerduty_routing_key",
    "notify_discord_enabled",
    "notify_discord_webhook",
    "notify_telegram_enabled",
    "notify_telegram_bot_token",
    "notify_telegram_chat_id",
    "notify_whatsapp_enabled",
    "notify_whatsapp_token",
    "notify_whatsapp_phone_id",
    "notify_whatsapp_to",
    "notify_whatsapp_template",
    "notify_whatsapp_template_lang",
    "servicenow_enabled",
    "servicenow_url",
    "servicenow_user",
    "servicenow_password",
    "smtp_host",
    "smtp_port",
    "smtp_user",
    "smtp_password",
    "smtp_from",
    "smtp_tls",
    "email_domain_restriction",
    "ping_interval",
    "incidents_enabled",
    "company_name",
]


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        status=user.status,
        must_change_password=bool(user.must_change_password),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        password_updated_at=user.password_updated_at,
        timezone=user.timezone,
    )


@router.get("/api/admin/users")
async def list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=TABLE_PAGE_SIZE, ge=1, le=100),
):
    query = select(User)
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one())
    page, page_size, pages, offset = page_bounds(page, page_size, total)
    users = (
        await db.execute(query.order_by(User.created_at.desc()).offset(offset).limit(page_size))
    ).scalars().all()
    return {
        "users": [_user_out(item) for item in users],
        "total": total,
        "page": page,
        "pages": pages,
        "page_size": page_size,
    }


@router.post("/api/admin/users/{user_id}/status")
async def set_user_status(
    user_id: int,
    request: Request,
    payload: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    status = payload.get("status")
    if status not in {"active", "disabled"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    if user.role == "admin" and status == "disabled":
        admins = int(
            (await db.execute(select(func.count(User.id)).where(User.role == "admin", User.status == "active"))).scalar_one()
        )
        if admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot disable the last admin")
    user.status = status
    await write_audit(db, "user_status", "%s -> %s" % (user.username, status), admin, request)
    await db.commit()
    return {"user": _user_out(user)}


@router.get("/api/admin/access-requests")
async def list_requests(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=TABLE_PAGE_SIZE, ge=1, le=100),
):
    query = select(AccessRequest)
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one())
    page, page_size, pages, offset = page_bounds(page, page_size, total)
    rows = (
        await db.execute(query.order_by(AccessRequest.created_at.desc()).offset(offset).limit(page_size))
    ).scalars().all()
    return {
        "requests": [
            {
                "id": row.id,
                "name": row.name,
                "email": row.email,
                "phone": row.phone,
                "status": row.status,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "pages": pages,
        "page_size": page_size,
    }


@router.post("/api/admin/access-requests/{request_id}/review")
async def review_request(
    request_id: int,
    payload: dict,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(AccessRequest, request_id)
    if not row or row.status != "pending":
        raise HTTPException(status_code=404, detail="Pending request not found")
    decision = payload.get("decision")
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be approved or rejected")
    row.status = decision
    row.reviewed_at = datetime.utcnow()
    row.reviewed_by = admin.id
    if decision == "approved":
        username = row.email
        db.add(
            User(
                username=username,
                name=row.name,
                email=row.email,
                phone=row.phone,
                password_hash=row.password_hash,
                role="user",
                status="active",
                must_change_password=0,
                approved_by_id=admin.id,
                updated_at=datetime.utcnow(),
                password_updated_at=datetime.utcnow(),
            )
        )
    await write_audit(db, "access_review", "%s %s" % (decision, row.email), admin, request)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Could not create that user")
    return {"ok": True}


@router.get("/api/admin/audit")
async def list_audit(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=TABLE_PAGE_SIZE, ge=1, le=100),
):
    query = select(AuditLog)
    if q.strip():
        like = "%" + q.strip() + "%"
        query = query.where(AuditLog.action.like(like) | AuditLog.actor.like(like) | AuditLog.detail.like(like))
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one())
    page, page_size, pages, offset = page_bounds(page, page_size, total)
    rows = (
        await db.execute(query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size))
    ).scalars().all()
    return {
        "total": total,
        "page": page,
        "pages": pages,
        "page_size": page_size,
        "logs": [
            {
                "id": row.id,
                "actor": row.actor,
                "action": row.action,
                "detail": row.detail,
                "ip_address": row.ip_address,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }


@router.get("/api/admin/settings")
async def get_settings(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return {"settings": redact_settings(await all_settings(db))}


@router.put("/api/admin/settings")
async def update_settings(
    payload: dict,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    incoming = payload.get("settings") or payload
    for key in EDITABLE_SETTINGS:
        if key not in incoming:
            continue
        value = incoming[key]
        if value == MASKED_SECRET:
            continue
        if key == "ping_interval":
            try:
                int(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Ping duration must be a number of seconds")
            value = str(clamp_ping_interval(value))
        if key == "incidents_enabled":
            value = "true" if str(value).lower() in {"1", "true", "yes", "on"} else "false"
        if key == "company_name":
            value = clean_company_name(value)
        await set_setting(db, key, "" if value is None else str(value))
    await write_audit(db, "settings_update", "Updated application settings", admin, request)
    await db.commit()
    return {"ok": True, "settings": redact_settings(await all_settings(db))}


@router.post("/api/admin/servicenow/test")
async def servicenow_test(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = test_connection(await all_settings(db))
    return {"result": result}


@router.post("/api/admin/notifications/test")
async def notification_test(
    payload: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    channel = str(payload.get("channel") or "").strip().lower()
    if channel not in CHANNELS:
        raise HTTPException(status_code=400, detail="Unknown notification channel")
    result = await test_channel(channel, await all_settings(db))
    return {"result": result, "channel": channel}


@router.patch("/api/devices/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: int,
    payload: DeviceUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DeviceOut:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    data = payload.model_dump(exclude_unset=True)
    monitor_keys = {
        "host",
        "monitor_type",
        "port",
        "dns_qtype",
        "dns_nameserver",
        "ws_path",
        "ws_secure",
        "grpc_service",
        "game_type",
    }
    monitor_in = {key: value for key, value in data.items() if key in monitor_keys}
    for key, value in data.items():
        if key not in monitor_keys:
            setattr(device, key, value)
    if monitor_in:
        try:
            apply_monitor_fields(device, monitor_in)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A monitor with that target already exists")
    await write_audit(db, "device_update", device.name, admin, request)
    await db.commit()
    await db.refresh(device)
    recent = await recent_by_device(db, [device.id], settings.sparkline_points)
    period = await stats_since(db, [device.id], datetime.utcnow() - RANGE_DELTA["24h"])
    return to_device_out(device, recent.get(device.id, []), period.get(device.id))
