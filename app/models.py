from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[Optional[str]] = mapped_column(String(6), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    host: Mapped[str] = mapped_column(String(253), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="server")
    monitor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="ping", server_default="ping")
    port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    monitor_spec: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    monitor_key: Mapped[str] = mapped_column(String(190), nullable=False, unique=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    service_mode: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rtt_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_change_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ssl_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    results: Mapped[List["PingResult"]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
        order_by="PingResult.checked_at",
    )


class SslHost(Base):
    __tablename__ = "ssl_hosts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    host: Mapped[str] = mapped_column(String(253), nullable=False, unique=True, index=True)
    ssl_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class PingResult(Base):
    __tablename__ = "ping_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    is_up: Mapped[int] = mapped_column(Integer, nullable=False)
    rtt_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)

    device: Mapped[Device] = relationship(back_populates="results")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(190), nullable=False, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    must_change_password: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    password_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(190), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")


INCIDENT_STATUSES = (
    "open",
    "active",
    "work_in_progress",
    "closed_successful",
    "closed_unsuccessful",
    "cancelled",
    "auto_resolved",
    "monitor",
    "pending",
)
LIVE_INCIDENT_STATUSES = (
    "open",
    "active",
    "work_in_progress",
    "monitor",
    "pending",
)
ARCHIVE_INCIDENT_STATUSES = (
    "closed_successful",
    "closed_unsuccessful",
    "cancelled",
    "auto_resolved",
)
ACTIVE_INCIDENT_STATUSES = LIVE_INCIDENT_STATUSES
CLOSED_INCIDENT_STATUSES = ARCHIVE_INCIDENT_STATUSES
INCIDENT_STATUS_LABELS = {
    "open": "Open",
    "active": "Active",
    "work_in_progress": "Work in progress",
    "closed_successful": "Closed successful",
    "closed_unsuccessful": "Closed unsuccessful",
    "cancelled": "Cancelled",
    "auto_resolved": "Auto resolved",
    "monitor": "Monitor",
    "pending": "Pending",
}
_INCIDENT_STATUS_ALIASES = {
    "acknowledged": "work_in_progress",
    "resolved": "closed_successful",
    "wip": "work_in_progress",
    "workinprogress": "work_in_progress",
    "closed_sucessfull": "closed_successful",
    "closed_successfull": "closed_successful",
    "closed_unsuccessfull": "closed_unsuccessful",
    "closed_unsucessfull": "closed_unsuccessful",
    "closed_unsucessful": "closed_unsuccessful",
    "autoresolved": "auto_resolved",
    "auto_resolve": "auto_resolved",
}


def canonicalize_incident_status(status: Optional[str]) -> str:
    value = (status or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _INCIDENT_STATUS_ALIASES.get(value, value)


def normalize_incident_status(status: Optional[str], fallback: str = "open") -> str:
    value = canonicalize_incident_status(status)
    return value if value in INCIDENT_STATUSES else fallback


def format_incident_number(incident_id: int) -> str:
    return "INC%07d" % int(incident_id)


def format_item_id(device_id: int) -> str:
    return "%06d" % (int(device_id) % 1000000)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, unique=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)
    active_ci_key: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    recovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    priority: Mapped[Optional[str]] = mapped_column(String(4), nullable=True, index=True)
    servicenow_sys_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    short_description: Mapped[Optional[str]] = mapped_column(String(190), nullable=True)


class IncidentNote(Base):
    __tablename__ = "incident_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    work_note: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)


class IncidentAttachment(Base):
    __tablename__ = "incident_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    filename: Mapped[str] = mapped_column(String(190), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(220), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False, default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="file")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)


class NasShare(Base):
    __tablename__ = "nas_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    name: Mapped[str] = mapped_column(String(190), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    storage: Mapped[Optional[str]] = mapped_column(String(190), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class StorageVolume(Base):
    __tablename__ = "storage_volumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    name: Mapped[str] = mapped_column(String(190), nullable=False)
    wwn: Mapped[str] = mapped_column(String(128), nullable=False)
    size: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    storage: Mapped[Optional[str]] = mapped_column(String(190), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    short_description: Mapped[str] = mapped_column(String(190), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="admin")
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)


class AnnouncementRead(Base):
    __tablename__ = "announcement_reads"

    announcement_id: Mapped[int] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

