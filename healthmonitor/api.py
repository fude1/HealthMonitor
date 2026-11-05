"""Web API FastAPI — contratto per la dashboard Casa/Monitor Salute."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from healthmonitor.config import AppConfig, load_config
from healthmonitor.engine import HealthEngine
from healthmonitor.version import ENGINE_VERSION, ENGINE_VERSION_NOTE


def create_app(cfg: AppConfig | None = None) -> FastAPI:
    config = cfg or load_config()
    engine = HealthEngine(config)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await engine.start()
        try:
            yield
        finally:
            await engine.stop()

    app = FastAPI(
        title="HealthMonitor",
        version=ENGINE_VERSION,
        description=ENGINE_VERSION_NOTE,
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.config = config

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def api_health() -> dict:
        return {"ok": True, "version": ENGINE_VERSION}

    @app.get("/api/status")
    async def api_status(request: Request):
        eng: HealthEngine = request.app.state.engine
        return eng.status().model_dump(mode="json")

    @app.get("/api/devices/huawei-gt3-pro")
    async def api_gt3(request: Request):
        eng: HealthEngine = request.app.state.engine
        return eng.device.model_dump(mode="json")

    @app.post("/api/devices/huawei-gt3-pro/sync")
    async def api_gt3_sync(request: Request):
        eng: HealthEngine = request.app.state.engine
        snap = await eng.sync_once()
        return snap.model_dump(mode="json")

    @app.get("/api/metrics/latest")
    async def api_metrics_latest(request: Request):
        """Alias dashboard-friendly: ultime metriche device primario."""
        eng: HealthEngine = request.app.state.engine
        snap = eng.device
        return {
            "device_label": snap.device_label,
            "source": snap.source,
            "synced_at": snap.synced_at.isoformat(),
            "online": snap.online,
            "metrics": [m.model_dump(mode="json") for m in snap.metrics],
            "error": snap.error,
            "notes": snap.notes,
        }

    return app
