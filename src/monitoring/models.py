from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

TargetType = Literal["http", "smtp", "dns"]


@dataclass(slots=True)
class Target:
    name: str
    type: TargetType
    timeout_seconds: int = 10
    url: str | None = None
    host: str | None = None
    port: int | None = None
    query: str | None = None


@dataclass(slots=True)
class CheckResult:
    target: str
    ok: bool
    reason: str
    checked_at: datetime


@dataclass(slots=True)
class IncidentState:
    target: str
    fail_count: int
    status: Literal["up", "down"]
    first_failed_at: datetime | None
    last_alert_at: datetime | None
    last_failure_reason: str | None


@dataclass(slots=True)
class AlertEvent:
    target: str
    severity: Literal["down", "recovery"]
    title: str
    body: str
