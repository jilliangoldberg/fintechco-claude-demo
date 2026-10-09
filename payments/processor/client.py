"""Acquirer (card processor) client.

The acquirer API does not deduplicate requests: every call to ``charge()`` is a
new authorization and capture.
"""

from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class ProcessorCharge:
    processor_charge_id: str
    processor_request_id: str


class ProcessorError(Exception):
    def __init__(self, processor_request_id: str, message: str = "") -> None:
        super().__init__(message or processor_request_id)
        self.processor_request_id = processor_request_id


class ProcessorDeclined(ProcessorError):
    """The issuer declined the card."""

    def __init__(self, processor_request_id: str, code: str) -> None:
        super().__init__(processor_request_id, f"declined: {code}")
        self.code = code


class ProcessorTimeout(ProcessorError):
    """No response from the acquirer within the configured timeout."""

    def __init__(self, processor_request_id: str, elapsed_ms: int) -> None:
        super().__init__(processor_request_id, f"timed out after {elapsed_ms} ms")
        self.elapsed_ms = elapsed_ms


class ProcessorClient(Protocol):
    def charge(
        self,
        *,
        processor_request_id: str,
        amount_minor: int,
        currency: str,
        card_token: str,
        metadata: dict[str, str],
    ) -> ProcessorCharge: ...

    def refund(
        self, *, processor_request_id: str, processor_charge_id: str, amount_minor: int
    ) -> str: ...


class HttpProcessorClient:
    """Client for the acquirer's REST API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._http = httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    def charge(
        self,
        *,
        processor_request_id: str,
        amount_minor: int,
        currency: str,
        card_token: str,
        metadata: dict[str, str],
    ) -> ProcessorCharge:
        body = {
            "amount": amount_minor,
            "currency": currency,
            "source": card_token,
            "capture": True,
            "metadata": metadata,
        }
        response = self._post("/charges", body, processor_request_id)
        if response.status_code == 402:
            code = response.json().get("decline_code", "generic_decline")
            raise ProcessorDeclined(processor_request_id, code)
        response.raise_for_status()
        return ProcessorCharge(response.json()["id"], processor_request_id)

    def refund(
        self, *, processor_request_id: str, processor_charge_id: str, amount_minor: int
    ) -> str:
        body = {"charge": processor_charge_id, "amount": amount_minor}
        response = self._post("/refunds", body, processor_request_id)
        response.raise_for_status()
        return response.json()["id"]

    def _post(self, path: str, body: dict, processor_request_id: str) -> httpx.Response:
        try:
            return self._http.post(path, json=body, headers={"X-Request-Id": processor_request_id})
        except httpx.TimeoutException as exc:
            elapsed_ms = int(self._timeout_seconds * 1000)
            raise ProcessorTimeout(processor_request_id, elapsed_ms) from exc
