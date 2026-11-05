"""Motore: sync periodico Huawei + snapshot in memoria per la Web API."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from healthmonitor.clients.huawei_health_kit import HuaweiHealthKitClient
from healthmonitor.config import AppConfig
from healthmonitor.models import DeviceSnapshot, EngineStatus, MetricPoint, utcnow
from healthmonitor.version import ENGINE_VERSION, ENGINE_VERSION_NOTE


def demo_snapshot(device_label: str) -> DeviceSnapshot:
    now = utcnow()
    return DeviceSnapshot(
        source="demo",
        device_label=device_label,
        synced_at=now,
        online=False,
        metrics=[
            MetricPoint(name="heart_rate", value=None, unit="bpm", recorded_at=None),
            MetricPoint(name="spo2", value=None, unit="%", recorded_at=None),
            MetricPoint(name="stress", value=None, unit="score", recorded_at=None),
            MetricPoint(name="steps", value=None, unit="steps", recorded_at=None),
        ],
        notes=[
            "Modalità demo: manca config Huawei (client_id/secret/refresh_token)",
            "Copia config.example.ini → config.ini e completa OAuth Health Kit",
            "GT3 Pro sincronizza via app Huawei Health; questo motore legge il cloud",
        ],
        error="huawei_not_configured",
    )


class HealthEngine:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self._started = time.monotonic()
        self._client = HuaweiHealthKitClient(cfg.huawei)
        self._device: DeviceSnapshot | None = None
        self._last_sync_at = None
        self._last_sync_ok: bool | None = None
        self._last_error: str | None = None
        self._task: asyncio.Task[Any] | None = None
        self._stop = asyncio.Event()

    @property
    def device(self) -> DeviceSnapshot:
        if self._device is not None:
            return self._device
        return demo_snapshot(self.cfg.huawei.device_label)

    def status(self) -> EngineStatus:
        return EngineStatus(
            version=ENGINE_VERSION,
            version_note=ENGINE_VERSION_NOTE,
            uptime_s=round(time.monotonic() - self._started, 1),
            huawei_configured=self.cfg.huawei.configured,
            last_sync_at=self._last_sync_at,
            last_sync_ok=self._last_sync_ok,
            last_error=self._last_error,
            device=self.device,
        )

    async def sync_once(self) -> DeviceSnapshot:
        if not self.cfg.huawei.configured:
            snap = demo_snapshot(self.cfg.huawei.device_label)
            self._device = snap
            self._last_sync_at = utcnow()
            self._last_sync_ok = False
            self._last_error = snap.error
            return snap

        snap = await self._client.fetch_snapshot(self.cfg.sync.lookback_hours)
        self._device = snap
        self._last_sync_at = snap.synced_at
        self._last_sync_ok = snap.error is None
        self._last_error = snap.error
        return snap

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.sync_once()
            except Exception as exc:  # noqa: BLE001
                self._last_error = str(exc)
                self._last_sync_ok = False
                self._last_sync_at = utcnow()
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=max(60, self.cfg.sync.interval_minutes * 60),
                )
            except TimeoutError:
                continue

    async def start(self) -> None:
        await self.sync_once()
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._loop(), name="health-sync")

    async def stop(self) -> None:
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
