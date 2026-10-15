"""Refund endpoints."""

from typing import Annotated

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from payments.api.errors import MissingIdempotencyKey
from payments.models import RefundRequest

router = APIRouter(prefix="/v1/charges", tags=["refunds"])


@router.post("/{charge_id}/refunds")
def create_refund(
    charge_id: str,
    body: RefundRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    if not idempotency_key:
        raise MissingIdempotencyKey()
    status, payload = request.app.state.refunds.create_refund(charge_id, body, idempotency_key)
    return JSONResponse(status_code=status, content=payload)
