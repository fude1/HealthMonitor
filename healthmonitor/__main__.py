"""Avvio: python -m healthmonitor"""

from __future__ import annotations

import uvicorn

from healthmonitor.config import load_config


def main() -> None:
    cfg = load_config()
    uvicorn.run(
        "healthmonitor.api:create_app",
        factory=True,
        host=cfg.server.host,
        port=cfg.server.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
