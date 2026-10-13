"""Application factory.

Run locally with ``uv run uvicorn payments.main:create_app --factory``.
"""

import os

from fastapi import FastAPI

from payments.api import charges, health
from payments.api.errors import register_error_handlers
from payments.api.middleware import RequestLogMiddleware
from payments.clock import Clock, SystemClock
from payments.db import connect
from payments.ids import Ids, RandomIds
from payments.log import EventLogger, configure_logging
from payments.processor.client import HttpProcessorClient, ProcessorClient
from payments.services.charges import ChargeService
from payments.services.idempotency import IdempotencyStore
from payments.services.ledger import Ledger
from payments.settings import Settings, load_settings


def create_app(
    settings: Settings | None = None,
    processor: ProcessorClient | None = None,
    clock: Clock | None = None,
    ids: Ids | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    clock = clock or SystemClock()
    ids = ids or RandomIds()
    if processor is None:
        processor = HttpProcessorClient(
            base_url=settings.processor.base_url,
            api_key=os.environ.get("PROCESSOR_API_KEY", ""),
            timeout_seconds=settings.processor.timeout_seconds,
        )

    configure_logging()
    conn = connect(settings.database_path)
    log = EventLogger(clock)
    ledger = Ledger(conn, ids, clock)

    app = FastAPI(title="payments-api", version="0.2.0")
    app.state.settings = settings
    app.state.ledger = ledger
    app.state.charges = ChargeService(
        conn=conn,
        processor=processor,
        idempotency=IdempotencyStore(conn, clock),
        ledger=ledger,
        ids=ids,
        clock=clock,
        log=log,
    )
    app.include_router(health.router)
    app.include_router(charges.router)
    register_error_handlers(app)
    app.add_middleware(RequestLogMiddleware, log=log, ids=ids, clock=clock)
    return app
