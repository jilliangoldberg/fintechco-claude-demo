"""Application factory.

Run locally with ``uv run uvicorn payments.main:create_app --factory``.
"""

from fastapi import FastAPI

from payments.api import health
from payments.clock import Clock, SystemClock
from payments.ids import Ids, RandomIds
from payments.settings import Settings, load_settings


def create_app(
    settings: Settings | None = None,
    clock: Clock | None = None,
    ids: Ids | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="payments-api", version="0.1.0")
    app.state.settings = settings
    app.state.clock = clock or SystemClock()
    app.state.ids = ids or RandomIds()
    app.include_router(health.router)
    return app
