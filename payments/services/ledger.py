"""Double-entry ledger.

Every money movement is posted as one transaction of balanced entries: per
currency, total debits equal total credits.

Accounts:
- ``processor_clearing``: money the acquirer owes us for captured charges
- ``customer_payments``: payments received from customers
"""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass

from payments.clock import Clock, isoformat
from payments.ids import Ids

PROCESSOR_CLEARING = "processor_clearing"
CUSTOMER_PAYMENTS = "customer_payments"


class UnbalancedTransaction(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    account: str
    direction: str  # "debit" or "credit"
    amount_minor: int
    currency: str


class Ledger:
    def __init__(self, conn: sqlite3.Connection, ids: Ids, clock: Clock) -> None:
        self._conn = conn
        self._ids = ids
        self._clock = clock

    def post(self, reference: str, entries: list[Entry]) -> str:
        """Post balanced entries as one transaction. Returns the transaction id."""
        totals: defaultdict[str, int] = defaultdict(int)
        for entry in entries:
            if entry.amount_minor <= 0:
                raise ValueError("ledger amounts must be positive")
            if entry.direction not in ("debit", "credit"):
                raise ValueError(f"unknown direction: {entry.direction}")
            sign = 1 if entry.direction == "debit" else -1
            totals[entry.currency] += sign * entry.amount_minor
        if any(totals.values()):
            raise UnbalancedTransaction(reference)

        txn_id = self._ids.new("txn")
        now = isoformat(self._clock.now())
        self._conn.executemany(
            "INSERT INTO ledger_entries"
            " (id, txn_id, reference, account, direction, amount_minor, currency, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    self._ids.new("le"),
                    txn_id,
                    reference,
                    entry.account,
                    entry.direction,
                    entry.amount_minor,
                    entry.currency,
                    now,
                )
                for entry in entries
            ],
        )
        return txn_id

    def post_charge(self, charge_id: str, amount_minor: int, currency: str) -> str:
        return self.post(
            charge_id,
            [
                Entry(PROCESSOR_CLEARING, "debit", amount_minor, currency),
                Entry(CUSTOMER_PAYMENTS, "credit", amount_minor, currency),
            ],
        )

    def post_refund(self, refund_id: str, amount_minor: int, currency: str) -> str:
        return self.post(
            refund_id,
            [
                Entry(CUSTOMER_PAYMENTS, "debit", amount_minor, currency),
                Entry(PROCESSOR_CLEARING, "credit", amount_minor, currency),
            ],
        )

    def balance(self, account: str, currency: str) -> int:
        """Debits minus credits for ``account``."""
        (total,) = self._conn.execute(
            "SELECT COALESCE(SUM(CASE direction WHEN 'debit' THEN amount_minor"
            " ELSE -amount_minor END), 0) FROM ledger_entries"
            " WHERE account = ? AND currency = ?",
            (account, currency),
        ).fetchone()
        return total

    def unbalanced_transactions(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT txn_id FROM ledger_entries GROUP BY txn_id, currency"
            " HAVING SUM(CASE direction WHEN 'debit' THEN amount_minor"
            " ELSE -amount_minor END) != 0"
        ).fetchall()
        return [row["txn_id"] for row in rows]
