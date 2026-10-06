"""Application factory.

Run locally with ``uv run uvicorn payments.main:create_app --factory``.
"""

from fastapi import FastAPI

from payments.api import health
from payments.api.middleware import RequestLogMiddleware
from payments.clock import Clock, SystemClock
from payments.ids import Ids, RandomIds
from payments.log import EventLogger, configure_logging
from payments.settings import Settings, load_settings


def create_app(
    settings: Settings | None = None,
    clock: Clock | None = None,
    ids: Ids | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    clock = clock or SystemClock()
    ids = ids or RandomIds()
    configure_logging()
    log = EventLogger(clock)

    app = FastAPI(title="payments-api", version="0.1.0")
    app.state.settings = settings
    app.include_router(health.router)
    app.add_middleware(RequestLogMiddleware, log=log, ids=ids, clock=clock)
    return app
