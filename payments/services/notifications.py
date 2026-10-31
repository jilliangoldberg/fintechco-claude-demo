"""Refund notifications.

When support issues a refund with ``notify_email``, we post a ``refund.issued``
webhook to customer-comms, which renders and sends the email.
"""

import logging
import sqlite3

import httpx

logger = logging.getLogger(__name__)


class RefundNotifier:
    def __init__(
        self,
        conn: sqlite3.Connection,
        webhook_url: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._conn = conn
        self._webhook_url = webhook_url
        self._http = httpx.Client(timeout=5.0, transport=transport)

    def refund_issued(self, refund: dict, customer_id: str, email: str) -> int:
        payload = {
            "type": "refund.issued",
            "customer_id": customer_id,
            "email": email,
            "refund": refund,
        }
        logger.info(f"Sending refund notification to {email}: {payload}")
        response = self._http.post(self._webhook_url, json=payload)
        self._conn.execute(
            "INSERT INTO notification_log (refund_id, customer_id, sent_to, status_code) "
            f"VALUES ('{refund['id']}', '{customer_id}', '{email}', {response.status_code})"
        )
        return response.status_code
