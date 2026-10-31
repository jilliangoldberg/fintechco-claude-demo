"""Refund notification endpoints, used by support tooling."""

from fastapi import APIRouter, HTTPException, Request

from payments.services.notifications import RefundNotFound

router = APIRouter(prefix="/v1/refunds", tags=["notifications"])


@router.post("/{refund_id}/notifications/resend", status_code=202)
def resend_refund_notification(refund_id: str, request: Request) -> dict:
    try:
        status = request.app.state.notifier.resend(refund_id)
    except RefundNotFound:
        raise HTTPException(status_code=404, detail="refund_not_found") from None
    return {"refund_id": refund_id, "webhook_status": status}
