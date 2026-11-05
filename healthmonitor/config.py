"""Carica config.ini (o env) senza segreti nel repo."""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INI = ROOT / "config.ini"
EXAMPLE_INI = ROOT / "config.example.ini"


@dataclass(frozen=True)
class HuaweiConfig:
    client_id: str
    client_secret: str
    refresh_token: str
    api_base: str
    oauth_token_url: str
    device_label: str

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)


@dataclass(frozen=True)
class SyncConfig:
    interval_minutes: int
    lookback_hours: int


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    huawei: HuaweiConfig
    sync: SyncConfig
    config_path: Path


def _section(cp: configparser.ConfigParser, name: str) -> configparser.SectionProxy:
    if name not in cp:
        cp[name] = {}
    return cp[name]


def load_config(path: Path | None = None) -> AppConfig:
    ini = path or Path(os.environ.get("HEALTHMONITOR_CONFIG", DEFAULT_INI))
    cp = configparser.ConfigParser()
    if ini.is_file():
        cp.read(ini, encoding="utf-8")
    elif EXAMPLE_INI.is_file():
        cp.read(EXAMPLE_INI, encoding="utf-8")

    srv = _section(cp, "server")
    hw = _section(cp, "huawei")
    sync = _section(cp, "sync")

    return AppConfig(
        server=ServerConfig(
            host=os.environ.get("HM_HOST", srv.get("host", "127.0.0.1")),
            port=int(os.environ.get("HM_PORT", srv.get("port", "8090"))),
        ),
        huawei=HuaweiConfig(
            client_id=os.environ.get("HUAWEI_CLIENT_ID", hw.get("client_id", "")).strip(),
            client_secret=os.environ.get(
                "HUAWEI_CLIENT_SECRET", hw.get("client_secret", "")
            ).strip(),
            refresh_token=os.environ.get(
                "HUAWEI_REFRESH_TOKEN", hw.get("refresh_token", "")
            ).strip(),
            api_base=os.environ.get(
                "HUAWEI_API_BASE",
                hw.get("api_base", "https://health-api.cloud.huawei.com/healthkit/v2"),
            ).rstrip("/"),
            oauth_token_url=os.environ.get(
                "HUAWEI_OAUTH_TOKEN_URL",
                hw.get(
                    "oauth_token_url",
                    "https://oauth-login.cloud.huawei.com/oauth2/v3/token",
                ),
            ),
            device_label=os.environ.get(
                "HUAWEI_DEVICE_LABEL",
                hw.get("device_label", "Huawei Watch GT 3 Pro"),
            ).strip()
            or "Huawei Watch GT 3 Pro",
        ),
        sync=SyncConfig(
            interval_minutes=int(
                os.environ.get("HM_SYNC_INTERVAL_MINUTES", sync.get("interval_minutes", "15"))
            ),
            lookback_hours=int(
                os.environ.get("HM_LOOKBACK_HOURS", sync.get("lookback_hours", "24"))
            ),
        ),
        config_path=ini,
    )
