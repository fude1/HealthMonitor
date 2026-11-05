"""Client REST Huawei Health Kit (dati GT3 Pro dopo sync Huawei Health).

Il Watch GT 3 Pro non espone un BLE aperto affidabile verso Windows.
Il percorso ufficiale è: orologio → app Huawei Health → Health Kit cloud API.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from healthmonitor.config import HuaweiConfig
from healthmonitor.models import DeviceSnapshot, MetricPoint, utcnow

# Tipi aperti tipici per GT3 Pro via Health Kit
DATA_TYPES: dict[str, tuple[str, str]] = {
    # name -> (dataTypeName, unit)
    "heart_rate": ("com.huawei.instantaneous.heart_rate", "bpm"),
    "spo2": ("com.huawei.instantaneous.spo2", "%"),
    "stress": ("com.huawei.instantaneous.stress", "score"),
    "steps": ("com.huawei.continuous.steps.delta", "steps"),
    "calories": ("com.huawei.continuous.calories.burnt", "kcal"),
    "sleep": ("com.huawei.continuous.sleep.fragment", "stage"),
}


class HuaweiHealthKitError(RuntimeError):
    pass


class HuaweiHealthKitClient:
    def __init__(self, cfg: HuaweiConfig, timeout_s: float = 30.0) -> None:
        self.cfg = cfg
        self._timeout = timeout_s
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    async def refresh_access_token(self) -> str:
        if not self.cfg.configured:
            raise HuaweiHealthKitError(
                "Huawei non configurato: client_id / client_secret / refresh_token mancanti"
            )
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.cfg.refresh_token,
            "client_id": self.cfg.client_id,
            "client_secret": self.cfg.client_secret,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self.cfg.oauth_token_url, data=data)
        if resp.status_code >= 400:
            raise HuaweiHealthKitError(
                f"OAuth refresh fallito ({resp.status_code}): {resp.text[:300]}"
            )
        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            raise HuaweiHealthKitError(f"OAuth senza access_token: {payload}")
        expires_in = int(payload.get("expires_in") or 3600)
        self._access_token = str(token)
        self._token_expires_at = time.time() + max(60, expires_in - 60)
        return self._access_token

    async def _bearer(self) -> str:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        return await self.refresh_access_token()

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-client-id": self.cfg.client_id,
        }

    async def polymerize(
        self,
        data_type_names: list[str],
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        token = await self._bearer()
        body = {
            "polymerizeWith": [{"dataTypeName": n} for n in data_type_names],
            "startTime": int(start.timestamp() * 1000),
            "endTime": int(end.timestamp() * 1000),
        }
        url = f"{self.cfg.api_base}/sampleSet:polymerize"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=self._headers(token), json=body)
        privacy = resp.headers.get("x-health-app-privacy")
        if privacy and privacy != "1":
            raise HuaweiHealthKitError(
                f"Privacy Huawei Health non concessa (x-health-app-privacy={privacy})"
            )
        if resp.status_code >= 400:
            raise HuaweiHealthKitError(
                f"polymerize fallito ({resp.status_code}): {resp.text[:400]}"
            )
        return resp.json()

    async def latest_sample_point(self, data_type: str) -> dict[str, Any] | None:
        token = await self._bearer()
        url = f"{self.cfg.api_base}/sampleSets/latestSamplePoint"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                url,
                headers=self._headers(token),
                params={"dataType": data_type},
            )
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise HuaweiHealthKitError(
                f"latestSamplePoint fallito ({resp.status_code}): {resp.text[:300]}"
            )
        return resp.json()

    @staticmethod
    def _pick_value(point: dict[str, Any]) -> float | int | str | None:
        value = point.get("value")
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                if "floatValue" in first:
                    return first["floatValue"]
                if "integerValue" in first:
                    return first["integerValue"]
                if "stringValue" in first:
                    return first["stringValue"]
            return first  # type: ignore[return-value]
        if isinstance(value, (int, float, str)):
            return value
        for key in ("floatValue", "integerValue", "stringValue"):
            if key in point:
                return point[key]
        return None

    @staticmethod
    def _pick_time(point: dict[str, Any]) -> datetime | None:
        for key in ("endTime", "startTime", "modifyTime"):
            raw = point.get(key)
            if raw is None:
                continue
            try:
                ms = int(raw)
                return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                continue
        return None

    def _flatten_polymerize(self, payload: dict[str, Any]) -> list[MetricPoint]:
        metrics: list[MetricPoint] = []
        groups = payload.get("group") or payload.get("sampleSet") or []
        if isinstance(payload.get("samplePoints"), list):
            groups = [{"sampleSet": [{"samplePoints": payload["samplePoints"]}]}]

        type_by_name = {v[0]: (k, v[1]) for k, v in DATA_TYPES.items()}

        for group in groups if isinstance(groups, list) else []:
            if not isinstance(group, dict):
                continue
            for sample_set in group.get("sampleSet") or []:
                if not isinstance(sample_set, dict):
                    continue
                dtype = (
                    (sample_set.get("dataTypeName") or "")
                    or ((sample_set.get("dataCollectorId") or "").split(":")[-1])
                )
                name_unit = type_by_name.get(dtype)
                points = sample_set.get("samplePoints") or []
                if not points:
                    continue
                # prendi l'ultimo punto del set
                last = points[-1] if isinstance(points[-1], dict) else None
                if not last:
                    continue
                name, unit = name_unit if name_unit else (dtype or "unknown", None)
                metrics.append(
                    MetricPoint(
                        name=name,
                        value=self._pick_value(last),
                        unit=unit,
                        recorded_at=self._pick_time(last),
                        raw={"dataTypeName": dtype},
                    )
                )
        return metrics

    async def fetch_snapshot(self, lookback_hours: int = 24) -> DeviceSnapshot:
        end = utcnow()
        start = end - timedelta(hours=max(1, lookback_hours))
        notes: list[str] = [
            "Percorso dati: GT3 Pro → Huawei Health (telefono) → Health Kit API",
            "BLE diretto non supportato in questo modulo",
        ]
        try:
            types = [v[0] for v in DATA_TYPES.values()]
            payload = await self.polymerize(types, start, end)
            metrics = self._flatten_polymerize(payload)

            # fallback: latest heart rate se polymerize vuoto
            if not any(m.name == "heart_rate" for m in metrics):
                latest = await self.latest_sample_point(
                    DATA_TYPES["heart_rate"][0]
                )
                if latest:
                    point = latest.get("samplePoint") or latest
                    if isinstance(point, dict):
                        metrics.append(
                            MetricPoint(
                                name="heart_rate",
                                value=self._pick_value(point),
                                unit="bpm",
                                recorded_at=self._pick_time(point),
                            )
                        )

            return DeviceSnapshot(
                source="huawei_gt3_pro",
                device_label=self.cfg.device_label,
                synced_at=utcnow(),
                online=True,
                metrics=metrics,
                notes=notes,
            )
        except Exception as exc:  # noqa: BLE001 — surface to snapshot
            return DeviceSnapshot(
                source="huawei_gt3_pro",
                device_label=self.cfg.device_label,
                synced_at=utcnow(),
                online=False,
                metrics=[],
                notes=notes,
                error=str(exc),
            )
