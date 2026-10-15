"""Refunds against existing charges, in full or as several partial refunds."""

import sqlite3

from payments.clock import Clock, isoformat
from payments.db import transaction
from payments.ids import Ids
from payments.log import EventLogger
from payments.models import RefundRequest
from payments.processor.client import ProcessorClient
from payments.services.charges import ChargeNotFound
from payments.services.idempotency import (
    IdempotencyConflict,
    IdempotencyKeyReused,
    IdempotencyStore,
    request_fingerprint,
)
from payments.services.ledger import Ledger


class RefundService:
    def __init__(
        self,
        *,
        conn: sqlite3.Connection,
        processor: ProcessorClient,
        idempotency: IdempotencyStore,
        ledger: Ledger,
        ids: Ids,
        clock: Clock,
        log: EventLogger,
    ) -> None:
        self._conn = conn
        self._processor = processor
        self._idempotency = idempotency
        self._ledger = ledger
        self._ids = ids
        self._clock = clock
        self._log = log

    def create_refund(
        self, charge_id: str, request: RefundRequest, idempotency_key: str
    ) -> tuple[int, dict]:
        """Refund ``request.amount_minor``, or whatever is left on the charge."""
        charge = self._conn.execute("SELECT * FROM charges WHERE id = ?", (charge_id,)).fetchone()
        if charge is None:
            raise ChargeNotFound(charge_id)
        customer_id = charge["customer_id"]

        # Refund keys share the customer's key space with charges, so namespace them.
        key = f"refund:{charge_id}:{idempotency_key}"
        request_hash = request_fingerprint({"charge_id": charge_id, **request.model_dump()})
        existing = self._idempotency.reserve(customer_id, key, request_hash)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyKeyReused(idempotency_key)
            if existing.status == "in_progress":
                raise IdempotencyConflict(idempotency_key)
            return existing.response_code, existing.response_body

        remaining = charge["amount_minor"] - self._refunded_minor(charge_id)
        amount = request.amount_minor or remaining
        if amount <= 0 or amount > remaining:
            body = {"error": "refund_exceeds_charge", "remaining_minor": remaining}
            self._idempotency.complete(customer_id, key, 422, body)
            return 422, body

        processor_refund_id = self._processor.refund(
            processor_request_id=self._ids.new("preq"),
            processor_charge_id=charge["processor_charge_id"],
            amount_minor=amount,
        )
        refund_id = self._ids.new("re")
        created_at = isoformat(self._clock.now())
        body = {
            "id": refund_id,
            "object": "refund",
            "charge_id": charge_id,
            "amount_minor": amount,
            "currency": charge["currency"],
            "reason": request.reason,
            "created_at": created_at,
        }
        with transaction(self._conn):
            self._conn.execute(
                "INSERT INTO refunds"
                " (id, charge_id, amount_minor, reason, processor_refund_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (refund_id, charge_id, amount, request.reason, processor_refund_id, created_at),
            )
            self._ledger.post_refund(refund_id, amount, charge["currency"])
            self._idempotency.complete(customer_id, key, 201, body)
        self._log.info(
            "refund.created",
            refund_id=refund_id,
            charge_id=charge_id,
            customer_id=customer_id,
            idempotency_key=idempotency_key,
            amount_minor=amount,
            currency=charge["currency"],
        )
        return 201, body

    def _refunded_minor(self, charge_id: str) -> int:
        (total,) = self._conn.execute(
            "SELECT COALESCE(SUM(amount_minor), 0) FROM refunds WHERE charge_id = ?",
            (charge_id,),
        ).fetchone()
        return total
