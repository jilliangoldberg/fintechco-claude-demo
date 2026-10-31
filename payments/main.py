"""Application factory.

Run locally with ``uv run uvicorn payments.main:create_app --factory``.
"""

import os

import httpx
from fastapi import FastAPI

from payments.api import charges, health, notifications, refunds
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
from payments.services.notifications import RefundNotifier
from payments.services.refunds import RefundService
from payments.settings import Settings, load_settings


def create_app(
    settings: Settings | None = None,
    processor: ProcessorClient | None = None,
    clock: Clock | None = None,
    ids: Ids | None = None,
    http_transport: httpx.BaseTransport | None = None,
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
    notifier = RefundNotifier(
        conn, settings.notifications.refund_webhook_url, transport=http_transport
    )
    services = {
        "conn": conn,
        "processor": processor,
        "idempotency": IdempotencyStore(conn, clock),
        "ledger": ledger,
        "ids": ids,
        "clock": clock,
        "log": log,
    }

    app = FastAPI(title="payments-api", version="0.5.0")
    app.state.settings = settings
    app.state.ledger = ledger
    app.state.charges = ChargeService(**services)
    app.state.refunds = RefundService(**services, notifier=notifier)
    app.state.notifier = notifier
    app.include_router(health.router)
    app.include_router(charges.router)
    app.include_router(refunds.router)
    app.include_router(notifications.router)
    register_error_handlers(app)
    app.add_middleware(RequestLogMiddleware, log=log, ids=ids, clock=clock)
    return app
