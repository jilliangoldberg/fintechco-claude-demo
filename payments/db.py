"""SQLite storage: schema and connection helpers."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS charges (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
    currency TEXT NOT NULL,
    card_last4 TEXT NOT NULL,
    processor_charge_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refunds (
    id TEXT PRIMARY KEY,
    charge_id TEXT NOT NULL REFERENCES charges (id),
    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
    reason TEXT,
    processor_refund_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    id TEXT PRIMARY KEY,
    txn_id TEXT NOT NULL,
    reference TEXT NOT NULL,
    account TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('debit', 'credit')),
    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
    currency TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ledger_entries_txn ON ledger_entries (txn_id);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    customer_id TEXT NOT NULL,
    key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed')),
    response_code INTEGER,
    response_body TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (customer_id, key)
);
"""


def connect(path: str) -> sqlite3.Connection:
    """Open the database and create the schema if needed.

    The connection runs in autocommit mode; group writes with ``transaction()``.
    """
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
