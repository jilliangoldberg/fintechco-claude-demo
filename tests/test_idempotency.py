import pytest

from payments.db import connect
from payments.services.idempotency import IdempotencyStore, request_fingerprint


@pytest.fixture
def store(clock) -> IdempotencyStore:
    return IdempotencyStore(connect(":memory:"), clock)


def test_fingerprint_ignores_field_order():
    assert request_fingerprint({"a": 1, "b": 2}) == request_fingerprint({"b": 2, "a": 1})


def test_reserve_new_key(store):
    assert store.reserve("cus_1", "key-1", "hash-1") is None

    record = store.get("cus_1", "key-1")
    assert record.status == "in_progress"
    assert record.request_hash == "hash-1"


def test_reserve_existing_key_returns_record(store):
    store.reserve("cus_1", "key-1", "hash-1")

    existing = store.reserve("cus_1", "key-1", "hash-1")

    assert existing is not None
    assert existing.status == "in_progress"


def test_complete_stores_response(store):
    store.reserve("cus_1", "key-1", "hash-1")
    store.complete("cus_1", "key-1", 201, {"id": "ch_1"})

    record = store.get("cus_1", "key-1")
    assert record.status == "completed"
    assert record.response_code == 201
    assert record.response_body == {"id": "ch_1"}
