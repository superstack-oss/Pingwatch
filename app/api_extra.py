from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.attachments import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS,
    attachment_kind,
    delete_stored,
    purge_incident_files,
    sanitize_filename,
    save_bytes,
    stored_path,
)
from app.config import settings
from app.db import get_db
from app.dnscheck import lookup_dns
from app.finder_csv import (
    SHARE_TEMPLATE,
    VOLUME_TEMPLATE,
    CsvError,
    parse_share_csv,
    parse_volume_csv,
)
from app.insight import build_insight, issue_priority, short_incident_description
from app.models import (
    ACTIVE_INCIDENT_STATUSES,
    ARCHIVE_INCIDENT_STATUSES,
    CLOSED_INCIDENT_STATUSES,
    INCIDENT_STATUS_LABELS,
    INCIDENT_STATUSES,
    LIVE_INCIDENT_STATUSES,
    Announcement,
    AnnouncementRead,
    Device,
    Incident,
    IncidentAttachment,
    IncidentNote,
    NasShare,
    PingResult,
    StorageVolume,
    User,
    canonicalize_incident_status,
    format_incident_number,
)
from app.pinger import ping_host
from app.queries import TABLE_PAGE_SIZE, page_bounds
from app.schemas import IncidentActionIn, IncidentNoteIn
from app.security import require_admin, require_user
from app.settings_store import write_audit
from app.stats import availability, display_status, rtt_stats

router = APIRouter()


@router.get("/api/analytics")
async def analytics(_: object = Depends(require_user), db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    day = now - timedelta(hours=24)
    counts = dict((await db.execute(select(Device.status, func.count(Device.id)).group_by(Device.status))).all())
    kinds = dict((await db.execute(select(Device.kind, func.count(Device.id)).group_by(Device.kind))).all())
    open_incidents = int(
        (
            await db.execute(select(func.count(Incident.id)).where(Incident.status.in_(ACTIVE_INCIDENT_STATUSES)))
        ).scalar_one()
    )
    resolved_24h = int(
        (
            await db.execute(
                select(func.count(Incident.id)).where(
                    Incident.status.in_(("closed_successful", "auto_resolved")),
                    Incident.recovered_at >= day,
                )
            )
        ).scalar_one()
    )
    sample_rows = (
        await db.execute(
            select(PingResult.is_up, PingResult.rtt_ms).where(PingResult.checked_at >= day)
        )
    ).all()
    mapped = [{"is_up": bool(row[0]), "rtt_ms": row[1]} for row in sample_rows]
    avg_rtt, _, _ = rtt_stats(mapped)
    devices = (await db.execute(select(Device).order_by(Device.name))).scalars().all()
    warning = 0
    kind_stats = {}
    health_map = []
    attention = []
    for device in devices:
        shown = display_status(device.status, device.rtt_ms, settings.warning_rtt_ms)
        if shown == "warning":
            warning += 1
        bucket = kind_stats.setdefault(
            device.kind, {"kind": device.kind, "total": 0, "healthy": 0, "attention": 0, "unknown": 0}
        )
        bucket["total"] += 1
        if shown == "online":
            bucket["healthy"] += 1
        elif shown == "unknown":
            bucket["unknown"] += 1
        else:
            bucket["attention"] += 1
        health_map.append(
            {"id": device.id, "name": device.name, "status": shown, "kind": device.kind}
        )
        if shown in {"offline", "warning"}:
            insight = build_insight(
                device.kind,
                device.host,
                status="down" if shown == "offline" else "up",
                rtt_ms=device.rtt_ms,
                warning_rtt_ms=settings.warning_rtt_ms,
            )
            attention.append(
                {
                    "id": device.id,
                    "name": device.name,
                    "kind": device.kind,
                    "status": shown,
                    "rtt_ms": device.rtt_ms,
                    "last_checked_at": device.last_checked_at,
                    "reason": (insight or {}).get("title") or ("Elevated latency" if shown == "warning" else "Unreachable"),
                }
            )
    slowest = (
        await db.execute(
            select(Device.id, Device.name, Device.host, Device.rtt_ms, Device.status)
            .where(Device.rtt_ms.is_not(None))
            .order_by(Device.rtt_ms.desc())
            .limit(8)
        )
    ).all()
    hourly = []
    for hour in range(23, -1, -1):
        start = now - timedelta(hours=hour + 1)
        end = now - timedelta(hours=hour)
        bucket = (
            await db.execute(
                select(
                    func.count(PingResult.id),
                    func.coalesce(func.sum(PingResult.is_up), 0),
                    func.avg(PingResult.rtt_ms),
                ).where(PingResult.checked_at >= start, PingResult.checked_at < end)
            )
        ).one()
        total, up_count = int(bucket[0] or 0), int(bucket[1] or 0)
        hourly.append(
            {
                "hour": start.isoformat(),
                "availability": round((up_count / total) * 100.0, 2) if total else None,
                "avg_rtt_ms": round(float(bucket[2]), 2) if bucket[2] is not None else None,
            }
        )
    up = int(counts.get("up", 0))
    down = int(counts.get("down", 0))
    unknown = int(counts.get("unknown", 0))
    return {
        "status": {"up": up, "down": down, "unknown": unknown, "warning": warning},
        "total": up + down + unknown,
        "kinds": kinds,
        "kind_cards": list(kind_stats.values()),
        "open_incidents": open_incidents,
        "resolved_24h": resolved_24h,
        "availability_24h": availability(mapped),
        "avg_rtt_ms": avg_rtt,
        "hourly": hourly,
        "health_map": health_map,
        "attention": attention[:TABLE_PAGE_SIZE],
        "slowest": [
            {"id": row[0], "name": row[1], "host": row[2], "rtt_ms": row[3], "status": row[4]}
            for row in slowest
        ],
    }


@router.get("/api/finder")
async def finder(
    q: str = "",
    live: bool = False,
    _: object = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Device)
    if q.strip():
        like = "%" + q.strip() + "%"
        query = query.where(Device.name.like(like) | Device.host.like(like) | Device.notes.like(like))
    devices = (await db.execute(query.order_by(Device.name).limit(50))).scalars().all()
    live_result = None
    if live and q.strip():
        host = q.strip()
        try:
            ping = await ping_host(host, 2.0)
            dns = await lookup_dns(host, force=True)
            live_result = {
                "host": host,
                "ping": {"is_up": ping.is_up, "rtt_ms": ping.rtt_ms, "error": ping.error},
                "dns": dns,
            }
        except Exception as exc:
            live_result = {"host": q.strip(), "error": str(exc)}
    return {
        "devices": [
            {
                "id": device.id,
                "name": device.name,
                "host": device.host,
                "kind": device.kind,
                "status": device.status,
                "rtt_ms": device.rtt_ms,
            }
            for device in devices
        ],
        "live": live_result,
    }


def _like(query: str):
    return "%" + query.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"


def _share_out(row: NasShare) -> dict:
    return {
        "id": row.id,
        "seq_no": row.seq_no,
        "name": row.name,
        "path": row.path,
        "description": row.description or "",
        "storage": row.storage or "",
    }


def _volume_out(row: StorageVolume) -> dict:
    return {
        "id": row.id,
        "seq_no": row.seq_no,
        "name": row.name,
        "wwn": row.wwn,
        "size": row.size or "",
        "storage": row.storage or "",
    }


@router.get("/api/finder/shares")
async def list_shares(
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=TABLE_PAGE_SIZE, ge=1, le=100),
    _: object = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(NasShare)
    term = q.strip()
    if term:
        like = _like(term)
        query = query.where(
            or_(
                NasShare.name.like(like),
                NasShare.path.like(like),
                NasShare.description.like(like),
                NasShare.storage.like(like),
            )
        )
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one())
    page, page_size, pages, offset = page_bounds(page, page_size, total)
    rows = (
        await db.execute(query.order_by(NasShare.seq_no.asc(), NasShare.name.asc()).offset(offset).limit(page_size))
    ).scalars().all()
    return {
        "kind": "shares",
        "items": [_share_out(row) for row in rows],
        "shown": len(rows),
        "total": total,
        "page": page,
        "pages": pages,
        "page_size": page_size,
    }


@router.get("/api/finder/volumes")
async def list_volumes(
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=TABLE_PAGE_SIZE, ge=1, le=100),
    _: object = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(StorageVolume)
    term = q.strip()
    if term:
        like = _like(term)
        query = query.where(
            or_(
                StorageVolume.name.like(like),
                StorageVolume.wwn.like(like),
                StorageVolume.size.like(like),
                StorageVolume.storage.like(like),
            )
        )
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one())
    page, page_size, pages, offset = page_bounds(page, page_size, total)
    rows = (
        await db.execute(
            query.order_by(StorageVolume.seq_no.asc(), StorageVolume.name.asc()).offset(offset).limit(page_size)
        )
    ).scalars().all()
    return {
        "kind": "volumes",
        "items": [_volume_out(row) for row in rows],
        "shown": len(rows),
        "total": total,
        "page": page,
        "pages": pages,
        "page_size": page_size,
    }


@router.get("/api/finder/shares/template.csv")
async def share_template(_: object = Depends(require_user)):
    return PlainTextResponse(
        SHARE_TEMPLATE,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="nas-shares-template.csv"'},
    )


@router.get("/api/finder/volumes/template.csv")
async def volume_template(_: object = Depends(require_user)):
    return PlainTextResponse(
        VOLUME_TEMPLATE,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="storage-volumes-template.csv"'},
    )


async def _read_csv_upload(file: UploadFile) -> bytes:
    filename = (file.filename or "").lower()
    if filename and not filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="The CSV file is empty")
    return payload


@router.post("/api/finder/shares/upload")
async def upload_shares(
    request: Request,
    file: UploadFile = File(...),
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    payload = await _read_csv_upload(file)
    try:
        rows, warnings = parse_share_csv(payload)
    except CsvError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.execute(delete(NasShare))
    for row in rows:
        db.add(NasShare(**row))
    await write_audit(db, "finder_shares_upload", "%s shares" % len(rows), admin, request)
    await db.commit()
    return {"kind": "shares", "imported": len(rows), "warnings": warnings[:12], "total": len(rows)}


@router.post("/api/finder/volumes/upload")
async def upload_volumes(
    request: Request,
    file: UploadFile = File(...),
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    payload = await _read_csv_upload(file)
    try:
        rows, warnings = parse_volume_csv(payload)
    except CsvError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.execute(delete(StorageVolume))
    for row in rows:
        db.add(StorageVolume(**row))
    await write_audit(db, "finder_volumes_upload", "%s volumes" % len(rows), admin, request)
    await db.commit()
    return {"kind": "volumes", "imported": len(rows), "warnings": warnings[:12], "total": len(rows)}


def _incident_out(incident: Incident, device: Device, user: Optional[User] = None) -> dict:
    number = incident.number or format_incident_number(incident.id)
    description = incident.description or incident.last_error or "Device is down."
    short = incident.short_description or short_incident_description(
        device.name,
        device.host,
        incident.last_error,
        monitor_type=getattr(device, "monitor_type", None),
    )
    duration = None
    live = incident.status in ACTIVE_INCIDENT_STATUSES
    end = incident.recovered_at or (datetime.utcnow() if live else None)
    if end:
        duration = max(0, int((end - incident.started_at).total_seconds()))
    verdict = issue_priority(device.kind, incident.last_error, failure_count=int(incident.failure_count or 1))
    priority = incident.priority or verdict["priority"]
    snow = incident.servicenow_sys_id if incident.servicenow_sys_id and not str(incident.servicenow_sys_id).startswith("local") else None
    return {
        "id": incident.id,
        "number": number,
        "status": incident.status,
        "priority": priority,
        "short_description": short,
        "description": description,
        "device_id": device.id,
        "device_name": device.name,
        "device_kind": device.kind,
        "ci": device.item_id or "%06d" % (device.id % 1000000),
        "host": device.host,
        "channel": "ServiceNow" if snow else "Pingwatch",
        "created_at": incident.started_at,
        "resolved_at": incident.recovered_at if incident.status in CLOSED_INCIDENT_STATUSES else None,
        "last_error": incident.last_error,
        "failure_count": incident.failure_count,
        "duration_seconds": duration,
        "servicenow_sys_id": snow,
        "actions": {
            "delete": bool(user and getattr(user, "role", None) == "admin"),
        },
    }


def _note_author(user: Optional[User] = None, actor: Optional[str] = None, user_id: Optional[int] = None) -> dict:
    if user is not None:
        username = (getattr(user, "username", None) or actor or "user").strip() or "user"
        role = "admin" if getattr(user, "role", "") == "admin" else "user"
        return {"actor": username, "username": username, "role": role}
    name = (actor or "system").strip() or "system"
    if user_id or name.lower() not in {"", "system"}:
        return {"actor": name, "username": name, "role": "user"}
    return {"actor": "system", "username": "system", "role": "system"}


def _note_out(note: IncidentNote, user: Optional[User] = None) -> dict:
    return {
        "id": note.id,
        "body": note.body,
        "work_note": bool(note.work_note),
        "created_at": note.created_at,
        **_note_author(user, getattr(note, "actor", None), getattr(note, "user_id", None)),
    }


def _apply_incident_status(db: AsyncSession, incident: Incident, status: Optional[str], user, now: datetime) -> str:
    new_status = canonicalize_incident_status(status)
    if new_status not in INCIDENT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid incident status")
    old = canonicalize_incident_status(incident.status)
    if old == new_status:
        return new_status
    incident.status = new_status
    if new_status in CLOSED_INCIDENT_STATUSES:
        if old not in CLOSED_INCIDENT_STATUSES:
            incident.recovered_at = now
        incident.active_ci_key = None
    else:
        incident.recovered_at = None
        incident.active_ci_key = incident.device_id
    _add_incident_note(
        db,
        incident.id,
        "Status changed to %s." % INCIDENT_STATUS_LABELS.get(new_status, new_status),
        actor=getattr(user, "username", None) or "system",
        user_id=getattr(user, "id", None),
        created_at=now,
    )
    return new_status


def _add_incident_note(
    db: AsyncSession,
    incident_id: int,
    body: str,
    *,
    actor: str = "system",
    user_id: Optional[int] = None,
    work_note: bool = True,
    created_at: Optional[datetime] = None,
) -> IncidentNote:
    note = IncidentNote(
        incident_id=incident_id,
        user_id=user_id,
        actor=actor or "system",
        body=body,
        work_note=1 if work_note else 0,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(note)
    return note


async def _incident_authors(db: AsyncSession, rows: list) -> dict:
    by_id = {}
    ids = {row.user_id for row in rows if getattr(row, "user_id", None)}
    if ids:
        found = (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all()
        by_id = {row.id: row for row in found}
    names = {
        (row.actor or "").strip()
        for row in rows
        if not by_id.get(getattr(row, "user_id", None)) and (row.actor or "").strip() and row.actor.strip().lower() != "system"
    }
    by_name = {}
    if names:
        extra = (await db.execute(select(User).where(User.username.in_(names)))).scalars().all()
        by_name = {row.username: row for row in extra}
    resolved = {}
    for row in rows:
        user = by_id.get(getattr(row, "user_id", None))
        if user is None and getattr(row, "actor", None):
            user = by_name.get(row.actor.strip())
        resolved[id(row)] = user
    return resolved


async def _incident_activities(db: AsyncSession, incident: Incident) -> list:
    rows = (
        await db.execute(
            select(IncidentNote).where(IncidentNote.incident_id == incident.id).order_by(IncidentNote.created_at.desc())
        )
    ).scalars().all()
    authors = await _incident_authors(db, rows)
    activities = [_note_out(row, authors.get(id(row))) for row in rows]
    opened = any("incident opened" in (item["body"] or "").lower() for item in activities)
    if not opened:
        activities.append(
            {
                "id": None,
                "body": "Incident opened.",
                "work_note": True,
                "created_at": incident.started_at,
                **_note_author(),
            }
        )
    activities.sort(key=lambda item: item["created_at"] or datetime.min, reverse=True)
    return activities


def _attachment_out(row: IncidentAttachment) -> dict:
    return {
        "id": row.id,
        "filename": row.filename,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "kind": row.kind,
        "actor": row.actor,
        "created_at": row.created_at,
        "url": "/api/incidents/%s/attachments/%s" % (row.incident_id, row.id),
    }


async def _incident_attachments(db: AsyncSession, incident_id: int) -> list:
    rows = (
        await db.execute(
            select(IncidentAttachment)
            .where(IncidentAttachment.incident_id == incident_id)
            .order_by(IncidentAttachment.created_at.desc())
        )
    ).scalars().all()
    return [_attachment_out(row) for row in rows]


@router.get("/api/incidents")
async def list_incidents(
    status: Optional[str] = None,
    scope: Optional[str] = None,
    device_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=TABLE_PAGE_SIZE, ge=1, le=100),
    user=Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    archive = scope == "archive"
    allowed = ARCHIVE_INCIDENT_STATUSES if archive else LIVE_INCIDENT_STATUSES
    query = select(Incident, Device).join(Device, Device.id == Incident.device_id)
    if device_id is not None:
        device = await db.get(Device, device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")
        query = query.where(Incident.device_id == device_id)
    if status in allowed:
        query = query.where(Incident.status == status)
    else:
        query = query.where(Incident.status.in_(allowed))
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one())
    page, page_size, pages, offset = page_bounds(page, page_size, total)
    rows = (await db.execute(query.order_by(Incident.started_at.desc()).offset(offset).limit(page_size))).all()
    payload = [_incident_out(incident, device, user) for incident, device in rows]
    open_query = select(func.count(Incident.id)).where(Incident.status.in_(LIVE_INCIDENT_STATUSES))
    archived_query = select(func.count(Incident.id)).where(Incident.status.in_(ARCHIVE_INCIDENT_STATUSES))
    if device_id is not None:
        open_query = open_query.where(Incident.device_id == device_id)
        archived_query = archived_query.where(Incident.device_id == device_id)
    open_count = int((await db.execute(open_query)).scalar_one())
    archived_count = int((await db.execute(archived_query)).scalar_one())
    return {
        "incidents": payload,
        "open": open_count,
        "archived": archived_count,
        "total": total,
        "scope": "archive" if archive else "live",
        "device_id": device_id,
        "page": page,
        "pages": pages,
        "page_size": page_size,
    }


@router.get("/api/incidents/{incident_id}")
async def get_incident(
    incident_id: int,
    user=Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    device = await db.get(Device, incident.device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    payload = _incident_out(incident, device, user)
    payload["activities"] = await _incident_activities(db, incident)
    payload["attachments"] = await _incident_attachments(db, incident.id)
    return {"incident": payload}


@router.post("/api/incidents/{incident_id}/notes")
async def add_incident_note(
    incident_id: int,
    payload: IncidentNoteIn,
    request: Request,
    user=Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    note = _add_incident_note(
        db,
        incident.id,
        payload.body,
        actor=user.username,
        user_id=user.id,
        work_note=payload.work_note,
    )
    await write_audit(db, "incident_note", "%s work note" % (incident.number or format_incident_number(incident.id)), user, request)
    await db.commit()
    await db.refresh(note)
    return {"note": _note_out(note, user)}


@router.post("/api/incidents/{incident_id}/attachments")
async def upload_incident_attachments(
    incident_id: int,
    request: Request,
    files: List[UploadFile] = File(...),
    user=Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    existing = int(
        (await db.execute(select(func.count(IncidentAttachment.id)).where(IncidentAttachment.incident_id == incident.id))).scalar_one()
    )
    saved = []
    for upload in files:
        kind = attachment_kind(upload.filename or "")
        if kind is None:
            raise HTTPException(status_code=400, detail="File type is not allowed")
        if existing + len(saved) >= MAX_ATTACHMENTS:
            raise HTTPException(status_code=400, detail="Too many attachments on this incident")
        payload = await upload.read()
        if not payload:
            raise HTTPException(status_code=400, detail="The selected file is empty")
        if len(payload) > MAX_ATTACHMENT_BYTES:
            raise HTTPException(status_code=400, detail="Each attachment must be 10 MB or smaller")
        filename = sanitize_filename(upload.filename or "attachment")
        stored, _path = save_bytes(incident.id, filename, payload)
        row = IncidentAttachment(
            incident_id=incident.id,
            user_id=user.id,
            actor=user.username,
            filename=filename,
            stored_name=stored,
            content_type=(upload.content_type or "application/octet-stream")[:120],
            size_bytes=len(payload),
            kind=kind,
        )
        db.add(row)
        saved.append(row)
        _add_incident_note(
            db,
            incident.id,
            "Attached %s." % filename,
            actor=user.username,
            user_id=user.id,
        )
    number = incident.number or format_incident_number(incident.id)
    await write_audit(db, "incident_attachment", "%s attached %s file(s)" % (number, len(saved)), user, request)
    await db.commit()
    for row in saved:
        await db.refresh(row)
    return {"attachments": [_attachment_out(row) for row in saved]}


@router.get("/api/incidents/{incident_id}/attachments/{attachment_id}")
async def download_incident_attachment(
    incident_id: int,
    attachment_id: int,
    _: object = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(IncidentAttachment, attachment_id)
    if row is None or row.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = stored_path(incident_id, row.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file is missing")
    inline = row.kind == "image"
    return FileResponse(
        path,
        media_type=row.content_type or "application/octet-stream",
        filename=row.filename,
        content_disposition_type="inline" if inline else "attachment",
    )


@router.delete("/api/incidents/{incident_id}/attachments/{attachment_id}")
async def delete_incident_attachment(
    incident_id: int,
    attachment_id: int,
    request: Request,
    user=Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(IncidentAttachment, attachment_id)
    if row is None or row.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    incident = await db.get(Incident, incident_id)
    filename = row.filename
    delete_stored(incident_id, row.stored_name)
    await db.delete(row)
    if incident is not None:
        _add_incident_note(
            db,
            incident.id,
            "Removed attachment %s." % filename,
            actor=user.username,
            user_id=user.id,
        )
        await write_audit(
            db,
            "incident_attachment_delete",
            "%s removed %s" % (incident.number or format_incident_number(incident.id), filename),
            user,
            request,
        )
    await db.commit()
    return {"ok": True, "deleted": attachment_id}


@router.patch("/api/incidents/{incident_id}")
async def update_incident(
    incident_id: int,
    payload: IncidentActionIn,
    request: Request,
    user=Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    now = datetime.utcnow()
    number = incident.number or format_incident_number(incident.id)
    next_status = None
    if payload.action == "delete":
        if getattr(user, "role", None) != "admin":
            raise HTTPException(status_code=403, detail="Only an admin can delete incidents")
        incident.active_ci_key = None
        await db.delete(incident)
        await write_audit(db, "incident_delete", number, user, request)
        await db.commit()
        purge_incident_files(incident_id)
        return {"ok": True, "deleted": incident_id}
    if payload.action == "acknowledge":
        next_status = "work_in_progress"
    elif payload.action == "resolve":
        next_status = "closed_successful"
    elif payload.action == "cancel":
        next_status = "cancelled"
    elif payload.action == "set_status":
        next_status = payload.status
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    _apply_incident_status(db, incident, next_status, user, now)

    await write_audit(
        db,
        "incident_status",
        "%s %s" % (number, incident.status),
        user,
        request,
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Another active incident already exists for this CI")
    await db.refresh(incident)
    device = await db.get(Device, incident.device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    detail = _incident_out(incident, device, user)
    detail["activities"] = await _incident_activities(db, incident)
    detail["attachments"] = await _incident_attachments(db, incident.id)
    return {"incident": detail}


def _announcement_out(row: Announcement, unread: bool) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "short_description": row.short_description,
        "body": row.body or "",
        "actor": row.actor,
        "created_at": row.created_at,
        "unread": unread,
    }


def _read_announcement_ids(user_id: int):
    return select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user_id)


async def _announcement_unread_count(db: AsyncSession, user_id: int) -> int:
    return int(
        (
            await db.execute(
                select(func.count(Announcement.id)).where(Announcement.id.notin_(_read_announcement_ids(user_id)))
            )
        ).scalar_one()
    )


@router.get("/api/announcements")
async def list_announcements(
    user=Depends(require_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=TABLE_PAGE_SIZE, ge=1, le=100),
    preview: int = Query(default=0, ge=0, le=20),
):
    query = select(Announcement)
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one())
    if preview:
        page, page_size, pages, offset = page_bounds(1, preview, total)
    else:
        page, page_size, pages, offset = page_bounds(page, page_size, total)
    rows = (
        await db.execute(
            query.order_by(Announcement.created_at.desc(), Announcement.id.desc()).offset(offset).limit(page_size)
        )
    ).scalars().all()
    read_ids = set(
        (await db.execute(select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user.id))).scalars().all()
    )
    unread = await _announcement_unread_count(db, user.id)
    return {
        "announcements": [_announcement_out(row, row.id not in read_ids) for row in rows],
        "total": total,
        "unread": unread,
        "page": page,
        "pages": pages,
        "page_size": page_size,
    }


@router.get("/api/announcements/unread-count")
async def announcement_unread_count(user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    return {"unread": await _announcement_unread_count(db, user.id)}


@router.get("/api/announcements/{announcement_id}")
async def get_announcement(announcement_id: int, user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    row = await db.get(Announcement, announcement_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    read = (
        await db.execute(
            select(AnnouncementRead).where(
                AnnouncementRead.announcement_id == announcement_id,
                AnnouncementRead.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    return {"announcement": _announcement_out(row, read is None)}


@router.post("/api/announcements/read-all")
async def mark_announcements_read(user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    existing = set(
        (await db.execute(select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user.id))).scalars().all()
    )
    rows = (await db.execute(select(Announcement.id))).scalars().all()
    now = datetime.utcnow()
    for announcement_id in rows:
        if announcement_id in existing:
            continue
        db.add(AnnouncementRead(announcement_id=announcement_id, user_id=user.id, read_at=now))
    await db.commit()
    return {"ok": True, "unread": 0}


@router.post("/api/announcements")
async def create_announcement(
    payload: dict,
    request: Request,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    title = (payload.get("title") or "").strip()
    short = (payload.get("short_description") or "").strip()
    body = (payload.get("body") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    if not short:
        raise HTTPException(status_code=400, detail="Short description is required")
    if len(title) > 120:
        raise HTTPException(status_code=400, detail="Title is too long")
    if len(short) > 190:
        raise HTTPException(status_code=400, detail="Short description is too long")
    if len(body) > 4000:
        raise HTTPException(status_code=400, detail="Message is too long")
    row = Announcement(
        title=title,
        short_description=short,
        body=body or None,
        actor=admin.name or admin.username,
        user_id=admin.id,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    await db.flush()
    await write_audit(db, "announcement_create", title, admin, request)
    await db.commit()
    await db.refresh(row)
    return {"announcement": _announcement_out(row, True)}


@router.post("/api/announcements/{announcement_id}/read")
async def mark_announcement_read(
    announcement_id: int,
    user=Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Announcement, announcement_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    existing = (
        await db.execute(
            select(AnnouncementRead).where(
                AnnouncementRead.announcement_id == announcement_id,
                AnnouncementRead.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(AnnouncementRead(announcement_id=announcement_id, user_id=user.id, read_at=datetime.utcnow()))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
    return {"ok": True}


@router.delete("/api/announcements/{announcement_id}")
async def delete_announcement(
    announcement_id: int,
    request: Request,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Announcement, announcement_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    title = row.title
    await db.execute(delete(AnnouncementRead).where(AnnouncementRead.announcement_id == announcement_id))
    await db.delete(row)
    await write_audit(db, "announcement_delete", title, admin, request)
    await db.commit()
    return {"ok": True}
