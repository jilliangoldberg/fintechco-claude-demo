"""Map domain errors to HTTP responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from payments.money import UnsupportedCurrency
from payments.processor.client import ProcessorError
from payments.services.charges import ChargeNotFound
from payments.services.idempotency import IdempotencyConflict, IdempotencyKeyReused


class MissingIdempotencyKey(Exception):
    pass


ERRORS: dict[type[Exception], tuple[int, str]] = {
    MissingIdempotencyKey: (400, "idempotency_key_required"),
    ChargeNotFound: (404, "charge_not_found"),
    IdempotencyConflict: (409, "request_in_progress"),
    IdempotencyKeyReused: (422, "idempotency_key_reused"),
    UnsupportedCurrency: (422, "unsupported_currency"),
    ProcessorError: (502, "processor_error"),
}


def register_error_handlers(app: FastAPI) -> None:
    for exc_type, (status, code) in ERRORS.items():
        app.add_exception_handler(exc_type, _handler(status, code))


def _handler(status: int, code: str):
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status, content={"error": code})

    return handle
