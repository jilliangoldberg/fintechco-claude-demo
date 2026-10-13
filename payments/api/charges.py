"""Charge endpoints."""

from typing import Annotated

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from payments.api.errors import MissingIdempotencyKey
from payments.models import ChargeRequest

router = APIRouter(prefix="/v1/charges", tags=["charges"])


@router.post("")
def create_charge(
    body: ChargeRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    if not idempotency_key:
        raise MissingIdempotencyKey()
    status, payload = request.app.state.charges.create_charge(body, idempotency_key)
    return JSONResponse(status_code=status, content=payload)


@router.get("/{charge_id}")
def get_charge(charge_id: str, request: Request) -> dict:
    return request.app.state.charges.get_charge(charge_id)
