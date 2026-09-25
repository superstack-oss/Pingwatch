from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.insight import build_insight
from app.models import Device, PingResult
from app.monitors import monitor_label, parse_spec, target_display
from app.schemas import DeviceDetailOut, DeviceOut, HistoryPoint, InsightOut, OutageOut
from app.stats import availability, compute_outages, display_status, last_event, rtt_stats

RANGE_DELTA = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

TABLE_PAGE_SIZE = 15


def page_bounds(page: int, page_size: int, total: int) -> tuple:
    page_size = min(100, max(1, int(page_size or TABLE_PAGE_SIZE)))
    pages = max(1, math.ceil(total / page_size)) if total else 1
    page = min(max(1, int(page or 1)), pages)
    offset = (page - 1) * page_size
    return page, page_size, pages, offset


def as_row(result: PingResult) -> Dict:
    return {
        "is_up": bool(result.is_up),
        "rtt_ms": result.rtt_ms,
        "error": result.error,
        "checked_at": result.checked_at,
    }


async def fetch_results(
    db: AsyncSession, device_id: int, since: Optional[datetime] = None, limit: Optional[int] = None
) -> List[PingResult]:
    query = select(PingResult).where(PingResult.device_id == device_id).order_by(PingResult.checked_at.asc())
    if since is not None:
        query = query.where(PingResult.checked_at >= since)
    if limit is not None:
        query = (
            select(PingResult)
            .where(PingResult.device_id == device_id)
            .order_by(PingResult.checked_at.desc())
            .limit(limit)
        )
        rows = list(reversed((await db.execute(query)).scalars().all()))
        return rows
    return list((await db.execute(query)).scalars().all())


async def fetch_checks_page(
    db: AsyncSession,
    device_id: int,
    since: datetime,
    page: int = 1,
    page_size: int = TABLE_PAGE_SIZE,
) -> tuple:
    page = max(1, int(page))
    page_size = min(50, max(5, int(page_size or TABLE_PAGE_SIZE)))
    total = int(
        (
            await db.execute(
                select(func.count(PingResult.id)).where(
                    PingResult.device_id == device_id,
                    PingResult.checked_at >= since,
                )
            )
        ).scalar_one()
        or 0
    )
    offset = (page - 1) * page_size
    rows = list(
        (
            await db.execute(
                select(PingResult)
                .where(PingResult.device_id == device_id, PingResult.checked_at >= since)
                .order_by(PingResult.checked_at.desc())
                .offset(offset)
                .limit(page_size)
            )
        ).scalars().all()
    )
    pages = max(1, (total + page_size - 1) // page_size) if total else 1
    return total, pages, page, page_size, rows


async def recent_by_device(db: AsyncSession, device_ids: Sequence[int], limit: int) -> Dict[int, List[PingResult]]:
    grouped: Dict[int, List[PingResult]] = defaultdict(list)
    if not device_ids:
        return grouped
    rn = func.row_number().over(
        partition_by=PingResult.device_id, order_by=PingResult.checked_at.desc()
    )
    subq = (
        select(
            PingResult.id,
            PingResult.device_id,
            PingResult.is_up,
            PingResult.rtt_ms,
            PingResult.error,
            PingResult.checked_at,
            rn.label("rn"),
        ).where(PingResult.device_id.in_(list(device_ids)))
    ).subquery()
    stmt = select(subq).where(subq.c.rn <= limit).order_by(subq.c.device_id, subq.c.checked_at)
    rows = (await db.execute(stmt)).all()
    for row in rows:
        grouped[row.device_id].append(
            PingResult(
                id=row.id,
                device_id=row.device_id,
                is_up=row.is_up,
                rtt_ms=row.rtt_ms,
                error=row.error,
                checked_at=row.checked_at,
            )
        )
    return grouped


async def stats_since(db: AsyncSession, device_ids: Sequence[int], since: datetime) -> Dict[int, Dict]:
    payload: Dict[int, Dict] = {}
    if not device_ids:
        return payload
    ids = list(device_ids)
    stmt = (
        select(
            PingResult.device_id,
            func.count(PingResult.id),
            func.coalesce(func.sum(PingResult.is_up), 0),
            func.avg(PingResult.rtt_ms),
            func.min(PingResult.rtt_ms),
            func.max(PingResult.rtt_ms),
        )
        .where(PingResult.device_id.in_(ids), PingResult.checked_at >= since)
        .group_by(PingResult.device_id)
    )
    for device_id, total, up_count, avg_rtt, min_rtt, max_rtt in (await db.execute(stmt)).all():
        payload[int(device_id)] = {
            "total": int(total or 0),
            "up_count": int(up_count or 0),
            "avg": float(avg_rtt) if avg_rtt is not None else None,
            "min": float(min_rtt) if min_rtt is not None else None,
            "max": float(max_rtt) if max_rtt is not None else None,
            "last_down_at": None,
            "last_up_at": None,
        }
    down_stmt = (
        select(PingResult.device_id, func.max(PingResult.checked_at))
        .where(PingResult.device_id.in_(ids), PingResult.is_up == 0)
        .group_by(PingResult.device_id)
    )
    for device_id, checked_at in (await db.execute(down_stmt)).all():
        if int(device_id) in payload:
            payload[int(device_id)]["last_down_at"] = checked_at
        else:
            payload[int(device_id)] = {
                "total": 0,
                "up_count": 0,
                "avg": None,
                "min": None,
                "max": None,
                "last_down_at": checked_at,
                "last_up_at": None,
            }
    up_stmt = (
        select(PingResult.device_id, func.max(PingResult.checked_at))
        .where(PingResult.device_id.in_(ids), PingResult.is_up == 1)
        .group_by(PingResult.device_id)
    )
    for device_id, checked_at in (await db.execute(up_stmt)).all():
        payload.setdefault(
            int(device_id),
            {
                "total": 0,
                "up_count": 0,
                "avg": None,
                "min": None,
                "max": None,
                "last_down_at": None,
                "last_up_at": None,
            },
        )["last_up_at"] = checked_at
    return payload


def to_device_out(
    device: Device,
    recent: Sequence[PingResult],
    period: Optional[Dict] = None,
) -> DeviceOut:
    period = period or {}
    history = [row.rtt_ms if row.is_up else None for row in recent][-settings.sparkline_points :]
    total = period.get("total") or 0
    up_count = period.get("up_count") or 0
    last_error = None
    for row in reversed(recent):
        if not row.is_up:
            last_error = row.error
            break
    last_down = period.get("last_down_at")
    last_up = period.get("last_up_at")
    if last_down is None:
        last_down = last_event([as_row(row) for row in recent], False)
    if last_up is None:
        last_up = last_event([as_row(row) for row in recent], True)
    paused = bool(getattr(device, "service_mode", 0))
    shown = "paused" if paused else display_status(device.status, device.rtt_ms, settings.warning_rtt_ms)
    monitor_type = getattr(device, "monitor_type", None) or "ping"
    spec = parse_spec(getattr(device, "monitor_spec", None))
    insight = None
    if not paused:
        raw = build_insight(
            device.kind,
            device.host,
            status=device.status,
            error=last_error,
            rtt_ms=device.rtt_ms,
            warning_rtt_ms=settings.warning_rtt_ms,
            monitor_type=monitor_type,
        )
        if raw:
            insight = InsightOut(**raw)
    return DeviceOut(
        id=device.id,
        item_id=device.item_id or "%06d" % (device.id % 1000000),
        ci=device.item_id or "%06d" % (device.id % 1000000),
        name=device.name,
        host=device.host,
        kind=device.kind,
        monitor_type=monitor_type,
        port=getattr(device, "port", None),
        monitor_spec=spec or None,
        monitor_label=monitor_label(monitor_type),
        target_display=target_display(monitor_type, device.host, getattr(device, "port", None), spec),
        notes=device.notes,
        status=device.status,  # type: ignore[arg-type]
        display_status=shown,  # type: ignore[arg-type]
        service_mode=paused,
        rtt_ms=device.rtt_ms,
        last_checked_at=device.last_checked_at,
        last_change_at=device.last_change_at,
        last_down_at=last_down,
        last_up_at=last_up,
        last_error=last_error,
        created_at=device.created_at,
        uptime_24h=round((up_count / total) * 100.0, 2) if total else None,
        avg_rtt_ms=round(period["avg"], 2) if period.get("avg") is not None else None,
        min_rtt_ms=round(period["min"], 2) if period.get("min") is not None else None,
        max_rtt_ms=round(period["max"], 2) if period.get("max") is not None else None,
        failure_count_24h=max(0, int(total) - int(up_count)) if total else 0,
        history=history,
        insight=insight,
    )


def history_points(rows: Iterable[PingResult]) -> List[HistoryPoint]:
    return [
        HistoryPoint(checked_at=row.checked_at, is_up=bool(row.is_up), rtt_ms=row.rtt_ms, error=row.error)
        for row in rows
    ]


def outages_from_rows(rows: Sequence[PingResult]) -> List[OutageOut]:
    incidents = compute_outages([as_row(row) for row in rows], now=datetime.utcnow())
    return [OutageOut(**item) for item in incidents]


async def to_detail(db: AsyncSession, device: Device) -> DeviceDetailOut:
    now = datetime.utcnow()
    rows_24h = await fetch_results(db, device.id, since=now - RANGE_DELTA["24h"])
    rows_7d = await fetch_results(db, device.id, since=now - RANGE_DELTA["7d"])
    rows_30d = await fetch_results(db, device.id, since=now - RANGE_DELTA["30d"])
    recent = rows_24h[-settings.sparkline_points :]
    base = to_device_out(
        device,
        recent,
        {
            "total": len(rows_24h),
            "up_count": sum(1 for row in rows_24h if row.is_up),
            "avg": rtt_stats([as_row(row) for row in rows_24h])[0],
            "min": rtt_stats([as_row(row) for row in rows_24h])[1],
            "max": rtt_stats([as_row(row) for row in rows_24h])[2],
            "last_down_at": last_event([as_row(row) for row in rows_30d], False),
            "last_up_at": last_event([as_row(row) for row in rows_30d], True),
        },
    )
    outages = outages_from_rows(rows_30d)
    last_outage = outages[0] if outages else None
    fail_7d = sum(1 for row in rows_7d if not row.is_up)
    fail_30d = sum(1 for row in rows_30d if not row.is_up)
    return DeviceDetailOut(
        **base.model_dump(),
        uptime_7d=availability([as_row(row) for row in rows_7d]),
        uptime_30d=availability([as_row(row) for row in rows_30d]),
        last_outage=last_outage,
        downtime_duration_seconds=last_outage.duration_seconds if last_outage else None,
        failure_count_7d=fail_7d,
        failure_count_30d=fail_30d,
    )


def search_clause(query: str):
    like = "%{}%".format(query.replace("%", r"\%").replace("_", r"\_"))
    return or_(
        Device.name.like(like),
        Device.host.like(like),
        Device.notes.like(like),
        Device.item_id.like(like),
        Device.monitor_type.like(like),
    )
