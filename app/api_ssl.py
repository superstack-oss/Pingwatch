from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import SslHost, User
from app.queries import TABLE_PAGE_SIZE, page_bounds
from app.schemas import SslHostCreate, SslHostListOut, SslHostOut, SslHostUpdate
from app.security import require_admin, require_user
from app.settings_store import all_settings, public_settings, write_audit
from app.ssl_report import build_ssl_report_pdf, report_filename
from app.sslcheck import refresh_ssl_host, ssl_host_payload

router = APIRouter()
STATUS_KEYS = {"valid", "expiring", "expired", "invalid", "unknown"}


def _as_out(row: SslHost) -> SslHostOut:
    return SslHostOut(**ssl_host_payload(row))


def _status_bucket(status: Optional[str]) -> str:
    value = (status or "Unknown").strip().lower()
    if value in STATUS_KEYS:
        return value
    return "invalid"


@router.get("/api/ssl", response_model=SslHostListOut)
async def list_ssl_hosts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_user),
    q: str = Query(default=""),
    status: Optional[str] = Query(default=None),
    sort: str = Query(default="name"),
    order: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=TABLE_PAGE_SIZE, ge=1, le=100),
) -> SslHostListOut:
    rows = (await db.execute(select(SslHost))).scalars().all()
    items = [_as_out(row) for row in rows]
    counts = {"valid": 0, "expiring": 0, "expired": 0, "invalid": 0}
    last_checked = None
    for item in items:
        bucket = _status_bucket(item.status)
        if bucket == "unknown":
            counts["invalid"] += 1
        elif bucket in counts:
            counts[bucket] += 1
        if item.last_checked_at and (last_checked is None or item.last_checked_at > last_checked):
            last_checked = item.last_checked_at

    needle = (q or "").strip().lower()
    filtered = items
    if needle:
        filtered = [
            item
            for item in filtered
            if needle in (item.name or "").lower()
            or needle in (item.host or "").lower()
            or needle in (item.issuer or "").lower()
            or needle in (item.provider or "").lower()
        ]
    wanted = (status or "").strip().lower()
    if wanted in STATUS_KEYS:
        filtered = [item for item in filtered if _status_bucket(item.status) == wanted]

    reverse = (order or "asc").lower() == "desc"
    sort_key = {
        "name": lambda item: (item.name or "").lower(),
        "host": lambda item: (item.host or "").lower(),
        "status": lambda item: (item.status or "").lower(),
        "issuer": lambda item: (item.provider or item.issuer or "").lower(),
        "days_left": lambda item: item.days_left if item.days_left is not None else 10**9,
        "not_after": lambda item: item.not_after or datetime.max,
        "domain_expires": lambda item: item.domain_expires or datetime.max,
        "last_checked_at": lambda item: item.last_checked_at or datetime.min,
    }.get(sort, lambda item: (item.name or "").lower())
    filtered.sort(key=sort_key, reverse=reverse)

    page, page_size, pages, offset = page_bounds(page, page_size, len(filtered))
    page_items = filtered[offset : offset + page_size]
    return SslHostListOut(
        hosts=page_items,
        total=len(items),
        filtered_total=len(filtered),
        valid=counts["valid"],
        expiring=counts["expiring"],
        expired=counts["expired"],
        invalid=counts["invalid"],
        last_checked_at=last_checked,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/api/ssl", response_model=SslHostOut)
async def create_ssl_host(
    payload: SslHostCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> SslHostOut:
    row = SslHost(name=payload.name or payload.host, host=payload.host)
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="That hostname is already on the SSL list")
    try:
        await refresh_ssl_host(row, force=True)
    except Exception:
        pass
    await db.commit()
    await write_audit(db, "ssl_create", row.host, admin, request)
    await db.commit()
    row = await db.get(SslHost, row.id)
    if not row:
        raise HTTPException(status_code=500, detail="SSL host was created but could not be reloaded")
    return _as_out(row)


@router.get("/api/ssl/{host_id}", response_model=SslHostOut)
async def get_ssl_host(
    host_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_user)
) -> SslHostOut:
    row = await db.get(SslHost, host_id)
    if not row:
        raise HTTPException(status_code=404, detail="SSL host not found")
    return _as_out(row)


@router.patch("/api/ssl/{host_id}", response_model=SslHostOut)
async def update_ssl_host(
    host_id: int,
    payload: SslHostUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> SslHostOut:
    row = await db.get(SslHost, host_id)
    if not row:
        raise HTTPException(status_code=404, detail="SSL host not found")
    previous_host = row.host
    host_changed = False
    if payload.host and payload.host != row.host:
        row.host = payload.host
        host_changed = True
    if payload.name is not None:
        row.name = payload.name or row.host
    elif host_changed and row.name == previous_host:
        row.name = row.host
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="That hostname is already on the SSL list")
    if host_changed:
        try:
            await refresh_ssl_host(row, force=True)
        except Exception:
            pass
    await write_audit(db, "ssl_update", row.host, admin, request)
    await db.commit()
    await db.refresh(row)
    return _as_out(row)


@router.get("/api/ssl/{host_id}/report.pdf")
async def ssl_host_report(
    host_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_user)
) -> Response:
    row = await db.get(SslHost, host_id)
    if not row:
        raise HTTPException(status_code=404, detail="SSL host not found")
    brand = public_settings(await all_settings(db))
    payload = ssl_host_payload(row)
    data = build_ssl_report_pdf(payload, brand)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="%s"' % report_filename(row.host)},
    )


@router.post("/api/ssl/{host_id}/refresh", response_model=SslHostOut)
async def refresh_ssl_host_endpoint(
    host_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_user)
) -> SslHostOut:
    row = await db.get(SslHost, host_id)
    if not row:
        raise HTTPException(status_code=404, detail="SSL host not found")
    await refresh_ssl_host(row, force=True)
    await db.commit()
    await db.refresh(row)
    return _as_out(row)


@router.delete("/api/ssl/{host_id}", status_code=204, response_class=Response)
async def delete_ssl_host(
    host_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Response:
    row = await db.get(SslHost, host_id)
    if not row:
        raise HTTPException(status_code=404, detail="SSL host not found")
    host = row.host
    await db.delete(row)
    await write_audit(db, "ssl_delete", host, admin, request)
    await db.commit()
    return Response(status_code=204)
