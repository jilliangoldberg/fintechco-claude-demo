from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from payments.clock import FakeClock
from payments.ids import SequentialIds
from payments.main import create_app
from payments.processor.mock import MockProcessor
from payments.settings import Settings


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 10, 1, 12, 0, tzinfo=UTC))


@pytest.fixture
def processor(clock) -> MockProcessor:
    return MockProcessor(clock=clock)


@pytest.fixture
def app(processor, clock):
    return create_app(settings=Settings(), processor=processor, clock=clock, ids=SequentialIds())


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def charge(client):
    """POST /v1/charges with a valid body. Keyword arguments override body fields."""

    def _charge(key: str = "key-1", **overrides):
        body = {
            "customer_id": "cus_1001",
            "amount_minor": 4250,
            "currency": "USD",
            "card_token": "tok_visa4417a",
            "card_last4": "4417",
        } | overrides
        return client.post("/v1/charges", json=body, headers={"Idempotency-Key": key})

    return _charge
