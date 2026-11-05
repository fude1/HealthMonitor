"""Modelli snapshot esposti alla dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MetricPoint(BaseModel):
    name: str
    value: float | int | str | None = None
    unit: str | None = None
    recorded_at: datetime | None = None
    raw: dict[str, Any] | None = None


class DeviceSnapshot(BaseModel):
    source: Literal["huawei_gt3_pro", "demo"] = "huawei_gt3_pro"
    device_label: str
    synced_at: datetime = Field(default_factory=utcnow)
    online: bool = False
    metrics: list[MetricPoint] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    error: str | None = None


class EngineStatus(BaseModel):
    version: str
    version_note: str
    uptime_s: float
    huawei_configured: bool
    last_sync_at: datetime | None = None
    last_sync_ok: bool | None = None
    last_error: str | None = None
    device: DeviceSnapshot | None = None
