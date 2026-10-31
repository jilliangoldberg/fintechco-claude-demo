import json

import httpx
import pytest
from fastapi.testclient import TestClient

from payments.ids import SequentialIds
from payments.main import create_app
from payments.processor.mock import MockProcessor
from payments.settings import Settings


@pytest.fixture
def webhooks() -> list[dict]:
    return []


@pytest.fixture
def client(clock, webhooks) -> TestClient:
    def handler(request: httpx.Request) -> httpx.Response:
        webhooks.append(json.loads(request.content))
        return httpx.Response(202)

    app = create_app(
        settings=Settings(),
        processor=MockProcessor(clock=clock),
        clock=clock,
        ids=SequentialIds(),
        http_transport=httpx.MockTransport(handler),
    )
    return TestClient(app)


def create_refund(client: TestClient, **body) -> httpx.Response:
    charge = client.post(
        "/v1/charges",
        json={
            "customer_id": "cus_1001",
            "amount_minor": 4250,
            "currency": "USD",
            "card_token": "tok_visa4417a",
            "card_last4": "4417",
        },
        headers={"Idempotency-Key": "key-1"},
    ).json()
    return client.post(
        f"/v1/charges/{charge['id']}/refunds", json=body, headers={"Idempotency-Key": "refund-1"}
    )


def test_refund_sends_notification(client, webhooks):
    response = create_refund(client, notify_email="pat@example.com")

    assert response.status_code == 201
    assert webhooks[0]["type"] == "refund.issued"
    assert webhooks[0]["refund"]["id"] == response.json()["id"]


def test_no_notification_without_email(client, webhooks):
    create_refund(client)

    assert webhooks == []


def test_resend_notification(client, webhooks):
    refund = create_refund(client, notify_email="pat@example.com").json()

    response = client.post(f"/v1/refunds/{refund['id']}/notifications/resend")

    assert response.status_code == 202
    assert len(webhooks) == 2
    assert webhooks[1]["refund"]["id"] == refund["id"]


def test_resend_unknown_refund_returns_404(client):
    response = client.post("/v1/refunds/re_missing/notifications/resend")

    assert response.status_code == 404
