from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from payments.clock import FakeClock
from payments.ids import SequentialIds
from payments.main import create_app
from payments.settings import Settings


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 10, 1, 12, 0, tzinfo=UTC))


@pytest.fixture
def app(clock):
    return create_app(settings=Settings(), clock=clock, ids=SequentialIds())


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)
