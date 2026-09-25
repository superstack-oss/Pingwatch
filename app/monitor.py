from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.mailer import notify
from app.models import ACTIVE_INCIDENT_STATUSES, Device, Incident, IncidentNote, PingResult, User, format_incident_number
from app.insight import (
    build_insight,
    issue_priority,
    should_create_ticket,
    should_open_incident,
    short_incident_description,
)
from app.monitors import down_phrase, probe_device
from app.servicenow import create_incident
from app.settings_store import all_settings, clamp_ping_interval, get_setting, setting_flag

log = logging.getLogger("pingwatch.monitor")
HISTORY_LIMIT = 40


def _flag(config: dict, key: str) -> bool:
    return str(config.get(key) or "").lower() in {"1", "true", "yes", "on"}


async def _send_alerts(session: AsyncSession, config: dict, subject: str, body: str) -> None:
    target = (config.get("notify_email") or "").strip()
    if target:
        await notify(session, target, subject, body)
        return
    admins = (
        await session.execute(select(User).where(User.role == "admin", User.status == "active"))
    ).scalars().all()
    for admin in admins:
        if admin.email:
            await notify(session, admin.email, subject, body)


class Monitor:
    def __init__(self) -> None:
        self.last_sweep_at: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        await asyncio.sleep(0.4)
        while True:
            try:
                await self.sweep()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Ping sweep failed")
            await asyncio.sleep(await self._interval())

    async def _interval(self) -> int:
        try:
            async with SessionLocal() as session:
                raw = await get_setting(session, "ping_interval", str(settings.ping_interval))
            return clamp_ping_interval(raw)
        except Exception:
            return settings.ping_interval

    async def sweep(self, device_id: Optional[int] = None) -> None:
        async with self._lock:
            async with SessionLocal() as session:
                query = select(Device)
                if device_id is not None:
                    query = query.where(Device.id == device_id)
                else:
                    query = query.where(Device.service_mode == 0)
                devices = (await session.execute(query)).scalars().all()
                if not devices:
                    if device_id is None:
                        self.last_sweep_at = datetime.utcnow()
                    return

                semaphore = asyncio.Semaphore(settings.ping_concurrency)

                async def probe(device: Device):
                    async with semaphore:
                        result = await probe_device(device, settings.ping_timeout)
                    return device, result

                outcomes = await asyncio.gather(*(probe(device) for device in devices))
                for device, outcome in outcomes:
                    await self._record(session, device, outcome.is_up, outcome.rtt_ms, outcome.error)
                await self._prune(session)
                await session.commit()
                if device_id is None:
                    self.last_sweep_at = datetime.utcnow()

    async def probe_one(self, device_id: int) -> None:
        await self.sweep(device_id=device_id)

    async def _record(
        self,
        session: AsyncSession,
        device: Device,
        is_up: bool,
        rtt: Optional[float],
        error: Optional[str],
    ) -> None:
        now = datetime.utcnow()
        status = "up" if is_up else "down"
        previous = device.status
        consecutive = 0
        if status == "down":
            consecutive = await self._consecutive_downs(session, device.id) + 1
        if previous != status:
            device.last_change_at = now
            if status == "up" and previous == "down":
                await self._close_incident(session, device, now)
        device.status = status
        device.rtt_ms = rtt if is_up else None
        device.last_checked_at = now
        session.add(
            PingResult(
                device_id=device.id,
                is_up=1 if is_up else 0,
                rtt_ms=rtt,
                error=error,
                checked_at=now,
            )
        )
        if status == "down":
            await self._handle_down(session, device, now, error, consecutive)

    async def _consecutive_downs(self, session: AsyncSession, device_id: int) -> int:
        rows = (
            (
                await session.execute(
                    select(PingResult.is_up)
                    .where(PingResult.device_id == device_id)
                    .order_by(PingResult.checked_at.desc(), PingResult.id.desc())
                    .limit(12)
                )
            )
            .scalars()
            .all()
        )
        count = 0
        for is_up in rows:
            if is_up:
                break
            count += 1
        return count

    async def _handle_down(
        self,
        session: AsyncSession,
        device: Device,
        now: datetime,
        error: Optional[str],
        consecutive: int,
    ) -> None:
        config = await all_settings(session)
        if not setting_flag(config, "incidents_enabled", True):
            return
        existing = await self._reuse_active(session, device, error)
        if existing:
            verdict = issue_priority(
                device.kind,
                error,
                failure_count=int(existing.failure_count or consecutive),
                monitor_type=getattr(device, "monitor_type", None),
            )
            existing.priority = verdict["priority"]
            await self._maybe_ticket(session, existing, device, error)
            return
        if not should_open_incident(device.kind, error, consecutive, monitor_type=getattr(device, "monitor_type", None)):
            return
        await self._open_incident(session, device, now, error, consecutive)

    async def _active_incidents(self, session: AsyncSession, device_id: int) -> List[Incident]:
        return list(
            (
                await session.execute(
                    select(Incident)
                    .where(
                        Incident.device_id == device_id,
                        Incident.status.in_(ACTIVE_INCIDENT_STATUSES),
                    )
                    .order_by(Incident.started_at.asc(), Incident.id.asc())
                )
            ).scalars().all()
        )

    async def _active_incident(self, session: AsyncSession, device_id: int) -> Optional[Incident]:
        rows = await self._active_incidents(session, device_id)
        return rows[0] if rows else None

    async def _reuse_active(self, session: AsyncSession, device: Device, error: Optional[str]) -> Optional[Incident]:
        rows = await self._active_incidents(session, device.id)
        if not rows:
            return None
        keep = rows[0]
        keep.failure_count = int(keep.failure_count or 1) + 1
        keep.active_ci_key = device.id
        if error:
            keep.last_error = error
        now = datetime.utcnow()
        for extra in rows[1:]:
            extra.status = "cancelled"
            extra.recovered_at = extra.recovered_at or now
            extra.active_ci_key = None
            keep.failure_count += int(extra.failure_count or 1)
        return keep

    async def _open_incident(
        self,
        session: AsyncSession,
        device: Device,
        now: datetime,
        error: Optional[str],
        consecutive: int,
    ) -> None:
        existing = await self._active_incident(session, device.id)
        if existing:
            existing.failure_count = int(existing.failure_count or 1) + 1
            existing.active_ci_key = device.id
            if error:
                existing.last_error = error
            await self._maybe_ticket(session, existing, device, error)
            return
        verdict = issue_priority(
            device.kind, error, failure_count=consecutive, monitor_type=getattr(device, "monitor_type", None)
        )
        insight = build_insight(
            device.kind,
            device.host,
            status="down",
            error=error,
            failure_count=consecutive,
            monitor_type=getattr(device, "monitor_type", None),
        )
        detail = (insight or {}).get("summary") or "CI %s (%s) is down. %s." % (
            device.name,
            device.host,
            down_phrase(getattr(device, "monitor_type", None), error),
        )
        if insight and insight.get("where"):
            detail = "%s\nWhere: %s" % (detail, insight["where"])
        if insight and insight.get("likely_cause"):
            detail = "%s\nLikely cause: %s" % (detail, insight["likely_cause"])
        detail = "%s\nPriority: %s" % (detail, verdict["priority"])
        short = short_incident_description(
            device.name,
            device.host,
            error,
            monitor_type=getattr(device, "monitor_type", None),
        )
        incident = Incident(
            device_id=device.id,
            status="open",
            started_at=now,
            last_error=error,
            description=detail,
            short_description=short,
            failure_count=consecutive,
            active_ci_key=device.id,
            priority=verdict["priority"],
        )
        session.add(incident)
        try:
            async with session.begin_nested():
                await session.flush()
        except IntegrityError:
            session.expunge(incident)
            existing = await self._reuse_active(session, device, error)
            if existing:
                await self._maybe_ticket(session, existing, device, error)
                return
            raise
        incident.number = format_incident_number(incident.id)
        session.add(
            IncidentNote(
                incident_id=incident.id,
                actor="system",
                body="Incident opened. %s" % (error or down_phrase(getattr(device, "monitor_type", None))),
                work_note=1,
                created_at=now,
            )
        )
        await self._maybe_ticket(session, incident, device, error)

    async def _maybe_ticket(
        self,
        session: AsyncSession,
        incident: Incident,
        device: Device,
        error: Optional[str],
    ) -> None:
        if incident.servicenow_sys_id:
            return
        if not should_create_ticket(
            device.kind,
            error or incident.last_error,
            int(incident.failure_count or 1),
            existing_sys_id=incident.servicenow_sys_id,
            monitor_type=getattr(device, "monitor_type", None),
        ):
            return
        config = await all_settings(session)
        number = incident.number or format_incident_number(incident.id or 0)
        priority = incident.priority or "P3"
        subject = "%s %s Pingwatch: %s is down" % (number, priority, device.name)
        detail = incident.description or "CI %s (%s) is down. %s." % (
            device.name,
            device.host,
            down_phrase(getattr(device, "monitor_type", None), error or incident.last_error),
        )
        snow_on = _flag(config, "servicenow_enabled")
        mailed = False
        try:
            sys_id = create_incident(
                config,
                subject,
                detail,
                urgency={"P1": "1", "P2": "2", "P3": "3"}.get(priority, "3"),
            )
            if sys_id:
                incident.servicenow_sys_id = sys_id
                mailed = True
            elif not snow_on:
                incident.servicenow_sys_id = "local"
                mailed = True
        except Exception:
            log.exception("ServiceNow incident create failed")
        if mailed and _flag(config, "notify_on_down"):
            await _send_alerts(session, config, subject, detail)

    async def _close_incident(self, session: AsyncSession, device: Device, now: datetime) -> None:
        rows = await self._active_incidents(session, device.id)
        if not rows:
            return
        keep = rows[0]
        keep.status = "auto_resolved"
        keep.recovered_at = now
        keep.active_ci_key = None
        session.add(
            IncidentNote(
                incident_id=keep.id,
                actor="system",
                body="CI %s (%s) is responding again. Incident auto resolved." % (device.name, device.host),
                work_note=1,
                created_at=now,
            )
        )
        for extra in rows[1:]:
            extra.status = "cancelled"
            extra.recovered_at = extra.recovered_at or now
            extra.active_ci_key = None
        config = await all_settings(session)
        if _flag(config, "notify_on_down") and not _flag(config, "notify_downtime_only"):
            detail = "CI %s (%s) is responding again." % (device.name, device.host)
            await _send_alerts(session, config, "Pingwatch: %s recovered" % device.name, detail)

    async def _prune(self, session: AsyncSession) -> None:
        cutoff = datetime.utcnow() - timedelta(days=settings.history_keep_days)
        await session.execute(delete(PingResult).where(PingResult.checked_at < cutoff))


monitor = Monitor()
