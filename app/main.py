from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
from starlette.middleware.sessions import SessionMiddleware

from app.api_admin import router as admin_router
from app.api_auth import router as auth_router
from app.api_extra import router as extra_router
from app.api_ssl import router as ssl_router
from app.config import settings
from app.db import SessionLocal, engine, get_db
from app.dnscheck import lookup_dns
from app.finder_csv import DEVICE_TEMPLATE, CsvError, parse_device_csv
from app.migrate import ensure_schema
from app.models import Device, Incident, SslHost, User, format_incident_number, format_item_id
from app.monitor import monitor
from app.monitors import apply_monitor_fields, catalog, MONITOR_TYPES, parse_spec
from app.netcheck import run_diagnostics
from app.queries import (
    RANGE_DELTA,
    TABLE_PAGE_SIZE,
    as_row,
    fetch_checks_page,
    fetch_results,
    history_points,
    outages_from_rows,
    page_bounds,
    recent_by_device,
    search_clause,
    stats_since,
    to_detail,
    to_device_out,
)
from app.schemas import (
    CheckLogOut,
    DeviceCreate,
    DeviceDetailOut,
    DeviceOut,
    FleetOut,
    HistoryOut,
    HistoryRange,
    OutageListOut,
    ServiceModeIn,
    SslOut,
)
from app.security import require_admin, require_user, user_from_session
from app.seed import seed_admin
from app.settings_store import seed_settings, write_audit
from app.sslcheck import refresh_device_ssl, ssl_view_for_device
from app.stats import availability, downsample, latency_trend, rtt_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pingwatch")

ROOT = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))
SORTABLE = {
    "item_id": Device.item_id,
    "name": Device.name,
    "host": Device.host,
    "kind": Device.kind,
    "monitor_type": Device.monitor_type,
    "status": Device.status,
    "rtt_ms": Device.rtt_ms,
    "last_checked_at": Device.last_checked_at,
}


async def _wait_for_mysql() -> None:
    delay = 1.0
    for attempt in range(30):
        try:
            await ensure_schema()
            return
        except OperationalError as exc:
            log.warning("Waiting for MySQL (%s/30): %s", attempt + 1, exc.orig or exc)
            await asyncio.sleep(delay)
            delay = min(delay * 1.4, 5)
    raise RuntimeError("Could not connect to MySQL")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await _wait_for_mysql()
    async with SessionLocal() as session:
        await seed_settings(session)
        await seed_admin(session)
    monitor.start()
    yield
    await monitor.stop()
    await engine.dispose()


app = FastAPI(title="Pingwatch", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="pingwatch",
    same_site="lax",
    https_only=False,
    max_age=60 * 60 * 24 * 7,
)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(extra_router)
app.include_router(ssl_router)
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


def _initials(user: Optional[User]) -> str:
    if not user:
        return "PW"
    source = (user.name or user.username or "PW").replace("@", " ")
    parts = [part for part in source.split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "PW"


async def _page_gate(request: Request, db: AsyncSession):
    user = await user_from_session(request, db)
    if user is None:
        return None, RedirectResponse("/login", status_code=302)
    request.state.user = user
    if user.must_change_password and request.url.path != "/password":
        return user, RedirectResponse("/password", status_code=302)
    return user, None


def _page(name: str, request: Request, extra: Optional[dict] = None) -> HTMLResponse:
    payload = extra or {}
    user = payload.get("user") or getattr(request.state, "user", None)
    context = {
        "request": request,
        "title": payload.get("title") or "Pingwatch",
        "nav": payload.get("nav") or "",
        "user": user,
        "user_initials": _initials(user),
    }
    context.update(payload)
    return templates.TemplateResponse(name, context)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    user = await user_from_session(request, db)
    if user and not user.must_change_password:
        return RedirectResponse("/", status_code=302)
    if user and user.must_change_password:
        return RedirectResponse("/password", status_code=302)
    return _page("login.html", request, {"title": "Sign in"})


@app.get("/request-access", response_class=HTMLResponse)
async def request_page(request: Request) -> HTMLResponse:
    return _page("request.html", request, {"title": "Request access"})


@app.get("/password", response_class=HTMLResponse)
async def password_page(request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    return _page("password.html", request, {"title": "Update password"})


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    return _page(
        "index.html",
        request,
        {
            "title": "Uptime",
            "nav": "dashboard",
            "lede": "Monitor NAS, storage, and server availability.",
        },
    )


@app.get("/ssl", response_class=HTMLResponse)
async def ssl_page(request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    return _page(
        "ssl.html",
        request,
        {
            "title": "SSL",
            "nav": "ssl",
            "lede": "Watch live certificates and domain registration expiry.",
        },
    )


@app.get("/ssl/{host_id}", response_class=HTMLResponse)
async def ssl_detail_page(host_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    row = await db.get(SslHost, host_id)
    if not row:
        raise HTTPException(status_code=404, detail="SSL host not found")
    return _page("ssl_detail.html", request, {"title": row.name, "ssl_id": row.id, "nav": "ssl"})


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    return _page(
        "analytics.html",
        request,
        {
            "title": "Overview Dashboard",
            "nav": "analytics",
            "lede": "Real-time summary of your entire monitored fleet.",
        },
    )


@app.get("/finder", response_class=HTMLResponse)
async def finder_page(request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    return _page(
        "finder.html",
        request,
        {"title": "Finder", "nav": "finder", "lede": "Look up NAS shares and storage volumes from the latest inventory CSV."},
    )


@app.get("/incidents", response_class=HTMLResponse)
async def incidents_page(request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    return _page(
        "incidents.html",
        request,
        {
            "title": "Incidents",
            "nav": "incidents",
            "lede": "Open and in-progress incidents that still need attention.",
            "archive": False,
            "device_id": None,
            "device_name": None,
            "device_ci": None,
        },
    )


@app.get("/devices/{device_id}/incidents", response_class=HTMLResponse)
async def device_incidents_page(device_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return _page(
        "incidents.html",
        request,
        {
            "title": "%s · Incidents" % device.name,
            "nav": "incidents",
            "lede": "Active incidents for this CI.",
            "archive": False,
            "device_id": device.id,
            "device_name": device.name,
            "device_ci": device.item_id or format_item_id(device.id),
        },
    )


@app.get("/archives", response_class=HTMLResponse)
async def archives_page(request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    return _page(
        "incidents.html",
        request,
        {
            "title": "Archives",
            "nav": "archives",
            "lede": "Closed, cancelled, and auto-resolved incidents.",
            "archive": True,
            "device_id": None,
            "device_name": None,
            "device_ci": None,
        },
    )


@app.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    return _page(
        "notifications.html",
        request,
        {
            "title": "Notifications",
            "nav": "notifications",
            "lede": "Announcements from your administrators.",
        },
    )


@app.get("/incidents/{incident_ref}", response_class=HTMLResponse)
async def incident_detail_page(incident_ref: str, request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    incident = None
    ref = (incident_ref or "").strip()
    if ref.isdigit():
        incident = await db.get(Incident, int(ref))
    else:
        incident = (
            await db.execute(select(Incident).where(Incident.number == ref.upper()))
        ).scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    number = incident.number or format_incident_number(incident.id)
    return _page(
        "incident.html",
        request,
        {
            "title": number,
            "nav": "incidents",
            "incident_id": incident.id,
            "incident_number": number,
            "lede": "Review the incident, add work notes, and update the status.",
        },
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    if user.role != "admin":
        return RedirectResponse("/", status_code=302)
    return _page(
        "admin.html",
        request,
        {"title": "Admin console", "nav": "admin", "lede": "Devices, users, audit logs, and workspace settings."},
    )


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    return _page(
        "profile.html",
        request,
        {"title": "User Details", "nav": "profile", "lede": "Profile, account lifecycle, and password controls."},
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    return _page(
        "settings.html",
        request,
        {"title": "Settings", "nav": "settings", "lede": "Display timezone, theme, and account preferences."},
    )


@app.get("/devices/{device_id}", response_class=HTMLResponse)
async def device_page(device_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return _page("device.html", request, {"title": device.name, "device_id": device.id, "nav": "dashboard"})


@app.get("/devices/{device_id}/investigate", response_class=HTMLResponse)
async def investigate_page(device_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user, redirect = await _page_gate(request, db)
    if redirect:
        return redirect
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return _page(
        "investigate.html",
        request,
        {"title": "%s · Investigate" % device.name, "device_id": device.id, "nav": "dashboard"},
    )


@app.get("/api/health")
async def health(db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "up"}


@app.get("/api/monitors/catalog")
async def monitor_catalog(_: User = Depends(require_user)):
    return catalog()


@app.get("/api/devices", response_model=FleetOut)
async def list_devices(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    q: str = Query(default=""),
    status: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    monitor_type: Optional[str] = Query(default=None),
    sort: str = Query(default="name"),
    order: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=TABLE_PAGE_SIZE, ge=1, le=100),
) -> FleetOut:
    counts = dict(
        (await db.execute(select(Device.status, func.count(Device.id)).group_by(Device.status))).all()
    )
    up = int(counts.get("up", 0))
    down = int(counts.get("down", 0))
    unknown = int(counts.get("unknown", 0))
    total = up + down + unknown

    query = select(Device)
    if q.strip():
        query = query.where(search_clause(q.strip()))
    if status in {"up", "down", "unknown"}:
        query = query.where(Device.status == status, Device.service_mode == 0)
    elif status == "warning":
        query = query.where(
            Device.status == "up",
            Device.rtt_ms >= settings.warning_rtt_ms,
            Device.service_mode == 0,
        )
    elif status == "paused":
        query = query.where(Device.service_mode == 1)
    if kind in {"nas", "server", "storage", "san", "network", "other"}:
        query = query.where(Device.kind == kind)
    if monitor_type in MONITOR_TYPES:
        query = query.where(Device.monitor_type == monitor_type)

    filtered = query.subquery()
    filtered_total = int((await db.execute(select(func.count()).select_from(filtered))).scalar_one())
    monitor_counts = {
        str(kind or "ping"): int(n)
        for kind, n in (
            await db.execute(select(filtered.c.monitor_type, func.count()).group_by(filtered.c.monitor_type))
        ).all()
    }
    page, page_size, pages, offset = page_bounds(page, page_size, filtered_total)
    column = SORTABLE.get(sort, Device.name)
    query = query.order_by(column.desc() if order == "desc" else column.asc())
    query = query.offset(offset).limit(page_size)
    devices = (await db.execute(query)).scalars().all()

    ids = [device.id for device in devices]
    recent = await recent_by_device(db, ids, settings.sparkline_points)
    period = await stats_since(db, ids, datetime.utcnow() - RANGE_DELTA["24h"])
    payloads = [to_device_out(device, recent.get(device.id, []), period.get(device.id)) for device in devices]
    warning = int(
        (
            await db.execute(
                select(func.count(Device.id)).where(
                    Device.status == "up", Device.rtt_ms >= settings.warning_rtt_ms
                )
            )
        ).scalar_one()
    )

    return FleetOut(
        devices=payloads,
        total=total,
        filtered_total=filtered_total,
        up=up,
        down=down,
        unknown=unknown,
        warning=warning,
        last_sweep_at=monitor.last_sweep_at,
        page=page,
        page_size=page_size,
        pages=pages,
        monitor_counts=monitor_counts,
    )


@app.post("/api/devices", response_model=DeviceOut)
async def create_device(
    payload: DeviceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> DeviceOut:
    device = Device(
        name=payload.name,
        host=payload.host,
        kind=payload.kind,
        notes=payload.notes,
        status="unknown",
        service_mode=0,
        monitor_type="ping",
        monitor_key="pending",
    )
    apply_monitor_fields(device, payload.model_dump())
    db.add(device)
    try:
        await db.flush()
        device.item_id = format_item_id(device.id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A monitor with that target already exists")
    device_id = device.id
    try:
        await monitor.probe_one(device_id)
    except Exception:
        log.exception("Immediate probe failed for device %s", device_id)
    await write_audit(db, "device_create", payload.name, admin, request)
    await db.commit()
    db.expire_all()
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=500, detail="Device was created but could not be reloaded")
    recent = await recent_by_device(db, [device.id], settings.sparkline_points)
    period = await stats_since(db, [device.id], datetime.utcnow() - RANGE_DELTA["24h"])
    return to_device_out(device, recent.get(device.id, []), period.get(device.id))


@app.get("/api/devices/template.csv")
async def device_template(_: User = Depends(require_user)):
    return PlainTextResponse(
        DEVICE_TEMPLATE,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="uptime-devices-template.csv"'},
    )


@app.post("/api/devices/upload")
async def upload_devices(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    filename = (file.filename or "").lower()
    if filename and not filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="The CSV file is empty")
    try:
        rows, warnings = parse_device_csv(payload)
    except CsvError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    existing = {
        str(key)
        for key in (await db.execute(select(Device.monitor_key))).scalars().all()
        if key
    }
    created = []
    for row in rows:
        if row["monitor_key"] in existing:
            warnings.append("Skipped existing monitor %s" % row["host"])
            continue
        existing.add(row["monitor_key"])
        device = Device(
            name=row["name"],
            host=row["host"],
            kind=row["kind"],
            notes=row["notes"],
            status="unknown",
            service_mode=0,
            monitor_type=row["monitor_type"],
            port=row.get("port"),
            monitor_spec=row.get("monitor_spec"),
            monitor_key=row["monitor_key"],
        )
        db.add(device)
        created.append(device)
    if created:
        try:
            await db.flush()
            for device in created:
                device.item_id = format_item_id(device.id)
            await write_audit(db, "device_csv_upload", "%s devices" % len(created), admin, request)
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail="One or more monitors already exist")
    return {
        "imported": len(created),
        "skipped": max(0, len(rows) - len(created)),
        "warnings": warnings[:12],
        "total": len(created),
    }


@app.get("/api/devices/{device_id}", response_model=DeviceDetailOut)
async def get_device(
    device_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_user)
) -> DeviceDetailOut:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return await to_detail(db, device)


@app.post("/api/devices/{device_id}/ssl", response_model=SslOut)
async def refresh_device_ssl_endpoint(
    device_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_user)
) -> SslOut:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await refresh_device_ssl(device, force=True, session=db)
    await db.commit()
    await db.refresh(device)
    return SslOut(**ssl_view_for_device(device))


@app.delete("/api/devices/{device_id}", status_code=204, response_class=Response)
async def delete_device(
    device_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Response:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    name = device.name
    await db.delete(device)
    await write_audit(db, "device_delete", name, admin, request)
    await db.commit()
    return Response(status_code=204)


@app.post("/api/devices/{device_id}/probe", response_model=DeviceOut)
async def probe_device(
    device_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_user)
) -> DeviceOut:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await monitor.probe_one(device.id)
    db.expire_all()
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    recent = await recent_by_device(db, [device.id], settings.sparkline_points)
    period = await stats_since(db, [device.id], datetime.utcnow() - RANGE_DELTA["24h"])
    return to_device_out(device, recent.get(device.id, []), period.get(device.id))


@app.post("/api/devices/{device_id}/service-mode", response_model=DeviceOut)
async def set_service_mode(
    device_id: int,
    payload: ServiceModeIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> DeviceOut:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.service_mode = 1 if payload.enabled else 0
    await write_audit(
        db,
        "device_service_mode",
        "%s=%s" % (device.name, "on" if payload.enabled else "off"),
        user,
        request,
    )
    await db.commit()
    db.expire_all()
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    recent = await recent_by_device(db, [device.id], settings.sparkline_points)
    period = await stats_since(db, [device.id], datetime.utcnow() - RANGE_DELTA["24h"])
    return to_device_out(device, recent.get(device.id, []), period.get(device.id))


@app.get("/api/devices/{device_id}/history", response_model=HistoryOut)
async def device_history(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    range: HistoryRange = Query(default="24h"),
) -> HistoryOut:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    rows = await fetch_results(db, device_id, since=datetime.utcnow() - RANGE_DELTA[range])
    mapped = [as_row(row) for row in rows]
    avg_rtt, min_rtt, max_rtt = rtt_stats(mapped)
    values = [row["rtt_ms"] for row in mapped if row["is_up"] and row["rtt_ms"] is not None]
    points = downsample(history_points(rows), 240)
    return HistoryOut(
        range=range,
        points=points,
        avg_rtt_ms=avg_rtt,
        min_rtt_ms=min_rtt,
        max_rtt_ms=max_rtt,
        current_rtt_ms=device.rtt_ms,
        availability=availability(mapped),
        trend=latency_trend(values),
        sample_count=len(rows),
    )


@app.get("/api/devices/{device_id}/checks", response_model=CheckLogOut)
async def device_checks(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    range: HistoryRange = Query(default="24h"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=TABLE_PAGE_SIZE, ge=5, le=50),
) -> CheckLogOut:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    total, pages, page, page_size, rows = await fetch_checks_page(
        db, device_id, datetime.utcnow() - RANGE_DELTA[range], page, page_size
    )
    return CheckLogOut(
        range=range,
        page=page,
        page_size=page_size,
        pages=pages,
        total=total,
        checks=history_points(rows),
    )


@app.get("/api/devices/{device_id}/outages", response_model=OutageListOut)
async def device_outages(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    range: HistoryRange = Query(default="30d"),
) -> OutageListOut:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    rows = await fetch_results(db, device_id, since=datetime.utcnow() - RANGE_DELTA[range])
    return OutageListOut(
        range=range,
        availability=availability([as_row(row) for row in rows]),
        outages=outages_from_rows(rows),
    )


@app.get("/api/devices/{device_id}/dns")
async def device_dns(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    refresh: bool = False,
) -> Dict:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return await lookup_dns(device.host, force=refresh)


@app.get("/api/devices/{device_id}/diagnostics")
async def device_diagnostics(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    traceroute: bool = False,
) -> Dict:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return await run_diagnostics(device.host, include_traceroute=traceroute, kind=device.kind)
