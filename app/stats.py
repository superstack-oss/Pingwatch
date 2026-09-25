from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def availability(rows: Sequence[Dict]) -> Optional[float]:
    if not rows:
        return None
    up_count = sum(1 for row in rows if row["is_up"])
    return round((up_count / len(rows)) * 100.0, 2)


def rtt_stats(rows: Sequence[Dict]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    values = [row["rtt_ms"] for row in rows if row["is_up"] and row["rtt_ms"] is not None]
    if not values:
        return None, None, None
    return round(sum(values) / len(values), 2), round(min(values), 2), round(max(values), 2)


def latency_trend(values: Sequence[float]) -> str:
    if len(values) < 6:
        return "flat"
    mid = len(values) // 2
    first = sum(values[:mid]) / float(mid)
    second = sum(values[mid:]) / float(len(values) - mid)
    if first <= 0:
        return "flat"
    delta = (second - first) / first
    if delta > 0.15:
        return "up"
    if delta < -0.15:
        return "down"
    return "flat"


def downsample(points, max_points=240):
    if len(points) <= max_points:
        return list(points)
    step = float(len(points)) / max_points
    picked = []
    index = 0.0
    while int(index) < len(points) and len(picked) < max_points:
        picked.append(points[int(index)])
        index += step
    if picked[-1] is not points[-1]:
        picked[-1] = points[-1]
    return picked


def last_event(rows: Sequence[Dict], is_up: bool) -> Optional[datetime]:
    for row in reversed(rows):
        if bool(row["is_up"]) is is_up:
            return row["checked_at"]
    return None


def compute_outages(rows: Iterable[Dict], now: Optional[datetime] = None) -> List[Dict]:
    incidents: List[Dict] = []
    current: Optional[Dict] = None
    for row in rows:
        down = not row["is_up"]
        if down:
            if current is None:
                current = {
                    "started_at": row["checked_at"],
                    "ended_at": None,
                    "recovered_at": None,
                    "last_error": row.get("error"),
                    "failure_count": 1,
                    "ongoing": True,
                }
            else:
                current["failure_count"] += 1
                if row.get("error"):
                    current["last_error"] = row.get("error")
            current["ended_at"] = row["checked_at"]
        elif current is not None:
            current["recovered_at"] = row["checked_at"]
            current["ongoing"] = False
            current["duration_seconds"] = _duration(
                current["started_at"], current["recovered_at"]
            )
            incidents.append(current)
            current = None
    if current is not None:
        current["duration_seconds"] = _duration(current["started_at"], now)
        incidents.append(current)
    incidents.reverse()
    return incidents


def _duration(start: datetime, end: Optional[datetime]) -> Optional[int]:
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds()))


def display_status(status: str, rtt_ms: Optional[float], warning_rtt_ms: float) -> str:
    if status == "down":
        return "offline"
    if status == "unknown":
        return "unknown"
    if status == "up" and rtt_ms is not None and rtt_ms >= warning_rtt_ms:
        return "warning"
    if status == "up":
        return "online"
    return "unknown"
