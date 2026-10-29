"""Card charges.

A charge is authorized and captured at the processor in a single call.
Charging is idempotent per customer and ``Idempotency-Key``: a retry with the
same key and body gets the original response instead of a second charge.
"""

import sqlite3
from datetime import datetime

from payments.clock import Clock, isoformat
from payments.db import transaction
from payments.ids import Ids
from payments.log import EventLogger
from payments.models import ChargeRequest
from payments.money import exponent
from payments.processor.client import ProcessorClient, ProcessorDeclined, ProcessorTimeout
from payments.services.idempotency import (
    IdempotencyKeyReused,
    IdempotencyRecord,
    IdempotencyStore,
    request_fingerprint,
)
from payments.services.ledger import Ledger


class ChargeNotFound(Exception):
    pass


class ChargeService:
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

    def create_charge(self, request: ChargeRequest, idempotency_key: str) -> tuple[int, dict]:
        """Charge the card at most once per idempotency key. Returns (status, body)."""
        exponent(request.currency)  # rejects unsupported currencies
        request_hash = request_fingerprint(request.fingerprint_fields())
        context = {
            "idempotency_key": idempotency_key,
            "customer_id": request.customer_id,
            "amount_minor": request.amount_minor,
            "currency": request.currency,
            "card_last4": request.card_last4,
        }
        self._log.info("charge.received", **context)

        existing = self._idempotency.get(request.customer_id, idempotency_key)
        if existing is not None and existing.status == "completed":
            return self._replay(existing, request_hash, context)

        processor_request_id = self._ids.new("preq")
        self._log.info("processor.request", processor_request_id=processor_request_id, **context)
        started = self._clock.now()
        try:
            result = self._processor.charge(
                processor_request_id=processor_request_id,
                amount_minor=request.amount_minor,
                currency=request.currency,
                card_token=request.card_token,
                metadata={"customer_id": request.customer_id, "idempotency_key": idempotency_key},
            )
        except ProcessorDeclined as exc:
            self._log.info(
                "processor.decline",
                processor_request_id=processor_request_id,
                decline_code=exc.code,
                elapsed_ms=self._elapsed_ms(started),
                **context,
            )
            self._log.info("charge.failed", reason="declined", **context)
            return 402, {"error": "card_declined", "decline_code": exc.code}
        except ProcessorTimeout:
            self._log.warning(
                "processor.timeout",
                processor_request_id=processor_request_id,
                elapsed_ms=self._elapsed_ms(started),
                **context,
            )
            self._log.warning("charge.failed", reason="processor_timeout", **context)
            return 504, {"error": "processor_timeout", "retryable": True}

        self._log.info(
            "processor.success",
            processor_request_id=processor_request_id,
            processor_charge_id=result.processor_charge_id,
            elapsed_ms=self._elapsed_ms(started),
            **context,
        )
        charge_id = self._ids.new("ch")
        created_at = isoformat(self._clock.now())
        body = {
            "id": charge_id,
            "object": "charge",
            "customer_id": request.customer_id,
            "amount_minor": request.amount_minor,
            "currency": request.currency,
            "card_last4": request.card_last4,
            "status": "succeeded",
            "processor_charge_id": result.processor_charge_id,
            "refunded_minor": 0,
            "created_at": created_at,
        }
        with transaction(self._conn):
            self._conn.execute(
                "INSERT INTO charges (id, customer_id, amount_minor, currency, card_last4,"
                " processor_charge_id, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    charge_id,
                    request.customer_id,
                    request.amount_minor,
                    request.currency,
                    request.card_last4,
                    result.processor_charge_id,
                    "succeeded",
                    created_at,
                ),
            )
            self._ledger.post_charge(charge_id, request.amount_minor, request.currency)
            self._idempotency.save_completed(
                request.customer_id, idempotency_key, request_hash, 201, body
            )
        self._log.info(
            "charge.created",
            charge_id=charge_id,
            processor_charge_id=result.processor_charge_id,
            **context,
        )
        return 201, body

    def get_charge(self, charge_id: str) -> dict:
        row = self._conn.execute("SELECT * FROM charges WHERE id = ?", (charge_id,)).fetchone()
        if row is None:
            raise ChargeNotFound(charge_id)
        (refunded,) = self._conn.execute(
            "SELECT COALESCE(SUM(amount_minor), 0) FROM refunds WHERE charge_id = ?",
            (charge_id,),
        ).fetchone()
        return {
            "id": row["id"],
            "object": "charge",
            "customer_id": row["customer_id"],
            "amount_minor": row["amount_minor"],
            "currency": row["currency"],
            "card_last4": row["card_last4"],
            "status": row["status"],
            "processor_charge_id": row["processor_charge_id"],
            "refunded_minor": refunded,
            "created_at": row["created_at"],
        }

    def _replay(
        self, record: IdempotencyRecord, request_hash: str, context: dict
    ) -> tuple[int, dict]:
        if record.request_hash != request_hash:
            raise IdempotencyKeyReused(record.key)
        self._log.info("charge.replayed", response_code=record.response_code, **context)
        return record.response_code, record.response_body

    def _elapsed_ms(self, started: datetime) -> int:
        return int((self._clock.now() - started).total_seconds() * 1000)
