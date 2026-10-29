"""Idempotency keys for mutating requests.

Clients send an ``Idempotency-Key`` header with every mutating request. Keys
are scoped to a customer. The first request with a key reserves it
(``in_progress``); when that request finishes, its response is stored
(``completed``) and replayed to any later request with the same key and body.
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass

from payments.clock import Clock, isoformat


class IdempotencyConflict(Exception):
    """Another request with this key is still in progress."""


class IdempotencyKeyReused(Exception):
    """The key was already used with a different request body."""


@dataclass(frozen=True)
class IdempotencyRecord:
    customer_id: str
    key: str
    request_hash: str
    status: str
    response_code: int | None
    response_body: dict | None


def request_fingerprint(fields: dict) -> str:
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class IdempotencyStore:
    def __init__(self, conn: sqlite3.Connection, clock: Clock) -> None:
        self._conn = conn
        self._clock = clock

    def get(self, customer_id: str, key: str) -> IdempotencyRecord | None:
        row = self._conn.execute(
            "SELECT * FROM idempotency_keys WHERE customer_id = ? AND key = ?",
            (customer_id, key),
        ).fetchone()
        if row is None:
            return None
        return IdempotencyRecord(
            customer_id=row["customer_id"],
            key=row["key"],
            request_hash=row["request_hash"],
            status=row["status"],
            response_code=row["response_code"],
            response_body=json.loads(row["response_body"]) if row["response_body"] else None,
        )

    def reserve(self, customer_id: str, key: str, request_hash: str) -> IdempotencyRecord | None:
        """Claim ``key`` for a new request.

        Returns None if the key was free and is now reserved by the caller,
        otherwise the existing record for the key.
        """
        now = isoformat(self._clock.now())
        try:
            self._conn.execute(
                "INSERT INTO idempotency_keys"
                " (customer_id, key, request_hash, status, created_at, updated_at)"
                " VALUES (?, ?, ?, 'in_progress', ?, ?)",
                (customer_id, key, request_hash, now, now),
            )
        except sqlite3.IntegrityError:
            return self.get(customer_id, key)
        return None

    def complete(self, customer_id: str, key: str, response_code: int, response_body: dict) -> None:
        self._conn.execute(
            "UPDATE idempotency_keys"
            " SET status = 'completed', response_code = ?, response_body = ?, updated_at = ?"
            " WHERE customer_id = ? AND key = ?",
            (
                response_code,
                json.dumps(response_body),
                isoformat(self._clock.now()),
                customer_id,
                key,
            ),
        )

    def save_completed(
        self,
        customer_id: str,
        key: str,
        request_hash: str,
        response_code: int,
        response_body: dict,
    ) -> None:
        now = isoformat(self._clock.now())
        self._conn.execute(
            "INSERT INTO idempotency_keys (customer_id, key, request_hash, status,"
            " response_code, response_body, created_at, updated_at)"
            " VALUES (?, ?, ?, 'completed', ?, ?, ?, ?)",
            (customer_id, key, request_hash, response_code, json.dumps(response_body), now, now),
        )
