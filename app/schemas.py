from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.monitors import empty_to_none, normalize_monitor
from app.pinger import validate_host

DeviceKind = Literal["nas", "server", "storage", "san", "network", "other"]
MonitorType = Literal["ping", "tcp", "dns", "websocket", "grpc", "game"]
DeviceStatus = Literal["up", "down", "unknown"]
DisplayStatus = Literal["online", "offline", "warning", "unknown", "paused"]
HistoryRange = Literal["24h", "7d", "30d"]


class InsightOut(BaseModel):
    code: str
    title: str
    summary: str
    where: str
    likely_cause: str
    checks: List[str]


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=253)
    kind: DeviceKind = "server"
    notes: Optional[str] = Field(default=None, max_length=500)
    monitor_type: MonitorType = "ping"
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    dns_qtype: Optional[str] = Field(default=None, max_length=16)
    dns_nameserver: Optional[str] = Field(default=None, max_length=253)
    ws_path: Optional[str] = Field(default=None, max_length=200)
    ws_secure: Optional[bool] = None
    grpc_service: Optional[str] = Field(default=None, max_length=190)
    game_type: Optional[str] = Field(default=None, max_length=64)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Name is required")
        return cleaned

    @field_validator("host")
    @classmethod
    def clean_host(cls, value: str) -> str:
        if value.strip().lower().startswith(("ws://", "wss://")):
            return value.strip()
        return validate_host(value)

    @field_validator(
        "notes",
        "dns_qtype",
        "dns_nameserver",
        "ws_path",
        "grpc_service",
        "game_type",
        mode="before",
    )
    @classmethod
    def clean_optional(cls, value: Optional[str]) -> Optional[str]:
        value = empty_to_none(value)
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("port", mode="before")
    @classmethod
    def clean_port(cls, value):
        value = empty_to_none(value)
        return None if value is None else value

    @field_validator("ws_secure", mode="before")
    @classmethod
    def clean_secure(cls, value):
        value = empty_to_none(value)
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "wss"}
        return bool(value)

    @model_validator(mode="after")
    def validate_monitor(self):
        normalize_monitor(
            host=self.host,
            monitor_type=self.monitor_type,
            port=self.port,
            dns_qtype=self.dns_qtype,
            dns_nameserver=self.dns_nameserver,
            ws_path=self.ws_path,
            ws_secure=self.ws_secure,
            grpc_service=self.grpc_service,
            game_type=self.game_type,
        )
        return self


class SslCertOut(BaseModel):
    not_after: Optional[datetime] = None
    not_before: Optional[datetime] = None
    issuer: Optional[str] = None
    provider: Optional[str] = None
    logo: Optional[str] = None
    subject: Optional[str] = None
    common_name: Optional[str] = None
    sans: List[str] = []
    serial: Optional[str] = None
    port: Optional[int] = None
    days_left: Optional[int] = None
    status: Optional[str] = None
    authorized: Optional[bool] = None
    checked_at: Optional[datetime] = None
    error: Optional[str] = None


class SslDomainOut(BaseModel):
    name: Optional[str] = None
    expires_at: Optional[datetime] = None
    registered_at: Optional[datetime] = None
    registrar: Optional[str] = None
    days_left: Optional[int] = None
    status: Optional[str] = None
    checked_at: Optional[datetime] = None
    error: Optional[str] = None


class SslOut(BaseModel):
    applicable: bool = False
    has_tls: bool = False
    has_domain: bool = False
    host: Optional[str] = None
    cert: Optional[SslCertOut] = None
    domain: Optional[SslDomainOut] = None


class SslHostCreate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    host: str = Field(min_length=1, max_length=253)

    @field_validator("name", mode="before")
    @classmethod
    def clean_ssl_name(cls, value: Optional[str]) -> Optional[str]:
        value = empty_to_none(value)
        if value is None:
            return None
        cleaned = " ".join(str(value).split())
        return cleaned or None

    @field_validator("host")
    @classmethod
    def clean_ssl_host(cls, value: str) -> str:
        from app.sslcheck import normalize_ssl_host

        return normalize_ssl_host(value)

    @model_validator(mode="after")
    def default_ssl_name(self):
        if not self.name:
            self.name = self.host
        return self


class SslHostUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    host: Optional[str] = Field(default=None, max_length=253)

    @field_validator("name", mode="before")
    @classmethod
    def clean_ssl_name(cls, value: Optional[str]) -> Optional[str]:
        value = empty_to_none(value)
        if value is None:
            return None
        cleaned = " ".join(str(value).split())
        return cleaned or None

    @field_validator("host", mode="before")
    @classmethod
    def clean_ssl_host(cls, value: Optional[str]) -> Optional[str]:
        value = empty_to_none(value)
        if value is None:
            return None
        from app.sslcheck import normalize_ssl_host

        return normalize_ssl_host(value)

    @model_validator(mode="after")
    def require_one_field(self):
        if self.name is None and self.host is None:
            raise ValueError("Provide a name or hostname")
        return self


class SslHostOut(BaseModel):
    id: int
    name: str
    host: str
    status: str = "Unknown"
    issuer: Optional[str] = None
    provider: Optional[str] = None
    logo: Optional[str] = None
    subject: Optional[str] = None
    days_left: Optional[int] = None
    not_after: Optional[datetime] = None
    not_before: Optional[datetime] = None
    domain_name: Optional[str] = None
    domain_expires: Optional[datetime] = None
    domain_days: Optional[int] = None
    domain_status: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    error: Optional[str] = None
    ssl: Optional[SslOut] = None


class SslHostListOut(BaseModel):
    hosts: List[SslHostOut]
    total: int
    filtered_total: int
    valid: int = 0
    expiring: int = 0
    expired: int = 0
    invalid: int = 0
    last_checked_at: Optional[datetime] = None
    page: int = 1
    page_size: int = 25
    pages: int = 1


class DeviceOut(BaseModel):
    id: int
    item_id: Optional[str] = None
    ci: Optional[str] = None
    name: str
    host: str
    kind: str
    monitor_type: str = "ping"
    port: Optional[int] = None
    monitor_spec: Optional[Dict[str, Any]] = None
    monitor_label: str = "Ping"
    target_display: Optional[str] = None
    notes: Optional[str]
    status: DeviceStatus
    display_status: DisplayStatus
    service_mode: bool = False
    rtt_ms: Optional[float]
    last_checked_at: Optional[datetime]
    last_change_at: Optional[datetime]
    last_down_at: Optional[datetime]
    last_up_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    resolved_ip: Optional[str] = None
    resolved_ips: List[str] = []
    uptime_24h: Optional[float]
    avg_rtt_ms: Optional[float]
    min_rtt_ms: Optional[float]
    max_rtt_ms: Optional[float]
    failure_count_24h: int = 0
    history: List[Optional[float]]
    insight: Optional[InsightOut] = None

    model_config = {"from_attributes": True}


class FleetOut(BaseModel):
    devices: List[DeviceOut]
    total: int
    filtered_total: int
    up: int
    down: int
    unknown: int
    warning: int
    last_sweep_at: Optional[datetime]
    page: int
    page_size: int
    pages: int
    monitor_counts: Dict[str, int] = {}


class HistoryPoint(BaseModel):
    checked_at: datetime
    is_up: bool
    rtt_ms: Optional[float]
    error: Optional[str] = None


class HistoryOut(BaseModel):
    range: HistoryRange
    points: List[HistoryPoint]
    avg_rtt_ms: Optional[float]
    min_rtt_ms: Optional[float]
    max_rtt_ms: Optional[float]
    current_rtt_ms: Optional[float]
    availability: Optional[float]
    trend: str
    sample_count: int


class CheckLogOut(BaseModel):
    range: HistoryRange
    page: int
    page_size: int
    pages: int
    total: int
    checks: List[HistoryPoint]


class OutageOut(BaseModel):
    started_at: datetime
    ended_at: Optional[datetime]
    recovered_at: Optional[datetime]
    duration_seconds: Optional[int]
    failure_count: int
    last_error: Optional[str]
    ongoing: bool


class OutageListOut(BaseModel):
    range: HistoryRange
    availability: Optional[float]
    outages: List[OutageOut]


class DeviceDetailOut(DeviceOut):
    uptime_7d: Optional[float] = None
    uptime_30d: Optional[float] = None
    last_outage: Optional[OutageOut] = None
    downtime_duration_seconds: Optional[int] = None
    failure_count_7d: int = 0
    failure_count_30d: int = 0
    ssl: Optional[SslOut] = None


class DeviceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    host: Optional[str] = Field(default=None, min_length=1, max_length=253)
    kind: Optional[DeviceKind] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    monitor_type: Optional[MonitorType] = None
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    dns_qtype: Optional[str] = Field(default=None, max_length=16)
    dns_nameserver: Optional[str] = Field(default=None, max_length=253)
    ws_path: Optional[str] = Field(default=None, max_length=200)
    ws_secure: Optional[bool] = None
    grpc_service: Optional[str] = Field(default=None, max_length=190)
    game_type: Optional[str] = Field(default=None, max_length=64)

    @field_validator("host")
    @classmethod
    def clean_host_update(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if value.strip().lower().startswith(("ws://", "wss://")):
            return value.strip()
        return validate_host(value)

    @field_validator(
        "notes",
        "dns_qtype",
        "dns_nameserver",
        "ws_path",
        "grpc_service",
        "game_type",
        mode="before",
    )
    @classmethod
    def clean_optional_update(cls, value: Optional[str]) -> Optional[str]:
        value = empty_to_none(value)
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("port", mode="before")
    @classmethod
    def clean_port_update(cls, value):
        value = empty_to_none(value)
        return None if value is None else value

    @field_validator("ws_secure", mode="before")
    @classmethod
    def clean_secure_update(cls, value):
        value = empty_to_none(value)
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "wss"}
        return bool(value)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=190)
    password: str = Field(min_length=1, max_length=200)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class AccessRequestIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=5, max_length=190)
    phone: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=8, max_length=200)


class ProfileIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[str] = Field(default=None, min_length=5, max_length=190)
    phone: Optional[str] = Field(default=None, max_length=32)


class PreferencesIn(BaseModel):
    timezone: Optional[str] = Field(default=None, min_length=1, max_length=64)


class IncidentActionIn(BaseModel):
    action: Literal["acknowledge", "resolve", "cancel", "delete", "set_status"]
    status: Optional[str] = None


class IncidentNoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    work_note: bool = True

    @field_validator("body")
    @classmethod
    def clean_note(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Note is required")
        return cleaned


class ServiceModeIn(BaseModel):
    enabled: bool


class ApproverOut(BaseModel):
    name: str
    email: str


class UserOut(BaseModel):
    id: int
    username: str
    name: str
    email: str
    phone: Optional[str]
    role: str
    status: str
    must_change_password: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime] = None
    password_updated_at: Optional[datetime] = None
    timezone: Optional[str] = None
    approved_by: Optional[ApproverOut] = None

    model_config = {"from_attributes": True}
