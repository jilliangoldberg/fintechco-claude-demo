"""In-memory processor for tests and local development.

Behaviors are queued and consumed one per ``charge()`` call; with nothing
queued, charges are approved. Supported behaviors:

- ``approve``
- ``decline:<code>``, e.g. ``decline:insufficient_funds``
- ``timeout_before_processing``: times out without charging the card
- ``timeout_after_success``: charges the card, then times out

With a clock that can ``advance()``, timeouts and ``latency_ms`` move it forward.
"""

import hashlib
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime

from payments.ids import Ids
from payments.processor.client import ProcessorCharge, ProcessorDeclined, ProcessorTimeout


@dataclass
class RecordedCharge:
    processor_charge_id: str
    processor_request_id: str
    created_at: datetime | None
    amount_minor: int
    currency: str
    card_token: str
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def card_fingerprint(self) -> str:
        return "fp_" + hashlib.sha256(self.card_token.encode()).hexdigest()[:16]


class MockProcessor:
    def __init__(
        self,
        behaviors: Iterable[str] = (),
        *,
        clock=None,
        ids: Ids | None = None,
        timeout_seconds: float = 10.0,
        latency_ms: Callable[[], int] | None = None,
    ) -> None:
        self._behaviors = deque(behaviors)
        self._clock = clock
        self._ids = ids
        self._timeout_seconds = timeout_seconds
        self.latency_ms = latency_ms
        self.requests: list[dict] = []
        self.charges: list[RecordedCharge] = []
        self.refunds: list[dict] = []

    def queue(self, *behaviors: str) -> None:
        self._behaviors.extend(behaviors)

    def charge(
        self,
        *,
        processor_request_id: str,
        amount_minor: int,
        currency: str,
        card_token: str,
        metadata: dict[str, str],
    ) -> ProcessorCharge:
        behavior = self._behaviors.popleft() if self._behaviors else "approve"
        self.requests.append(
            {
                "processor_request_id": processor_request_id,
                "amount_minor": amount_minor,
                "currency": currency,
                "metadata": dict(metadata),
                "behavior": behavior,
            }
        )
        if behavior == "timeout_before_processing":
            raise self._timeout(processor_request_id)
        if behavior.startswith("decline"):
            self._wait()
            raise ProcessorDeclined(processor_request_id, behavior.partition(":")[2] or "declined")
        if behavior not in ("approve", "timeout_after_success"):
            raise ValueError(f"unknown mock processor behavior: {behavior}")

        recorded = RecordedCharge(
            processor_charge_id=self._new_id("pch", len(self.charges) + 1),
            processor_request_id=processor_request_id,
            created_at=self._clock.now() if self._clock else None,
            amount_minor=amount_minor,
            currency=currency,
            card_token=card_token,
            metadata=dict(metadata),
        )
        self.charges.append(recorded)
        if behavior == "timeout_after_success":
            raise self._timeout(processor_request_id)
        self._wait()
        return ProcessorCharge(recorded.processor_charge_id, processor_request_id)

    def refund(
        self, *, processor_request_id: str, processor_charge_id: str, amount_minor: int
    ) -> str:
        refund_id = self._new_id("pre", len(self.refunds) + 1)
        self.refunds.append(
            {
                "processor_refund_id": refund_id,
                "processor_request_id": processor_request_id,
                "processor_charge_id": processor_charge_id,
                "amount_minor": amount_minor,
            }
        )
        self._wait()
        return refund_id

    def _new_id(self, prefix: str, sequence: int) -> str:
        return self._ids.new(prefix) if self._ids else f"{prefix}_{sequence:04d}"

    def _timeout(self, processor_request_id: str) -> ProcessorTimeout:
        self._advance(self._timeout_seconds)
        return ProcessorTimeout(processor_request_id, int(self._timeout_seconds * 1000))

    def _wait(self) -> None:
        if self.latency_ms is not None:
            self._advance(self.latency_ms() / 1000)

    def _advance(self, seconds: float) -> None:
        if self._clock is not None and hasattr(self._clock, "advance"):
            self._clock.advance(seconds)
