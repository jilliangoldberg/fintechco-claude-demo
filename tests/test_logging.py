import json
import logging

import pytest

from payments.log import EventLogger


@pytest.fixture
def events(caplog):
    caplog.set_level(logging.INFO, logger="payments")

    def _events() -> list[dict]:
        return [json.loads(r.getMessage()) for r in caplog.records if r.name == "payments"]

    return _events


def test_request_id_is_echoed(client):
    response = client.get("/healthz", headers={"X-Request-Id": "req_test"})

    assert response.headers["x-request-id"] == "req_test"


def test_charge_logs_event_sequence(charge, events):
    charge()

    assert [e["event"] for e in events()] == [
        "http.request",
        "charge.received",
        "processor.request",
        "processor.success",
        "charge.created",
        "http.response",
    ]


def test_log_lines_carry_request_id(client, events):
    body = {
        "customer_id": "cus_1001",
        "amount_minor": 4250,
        "currency": "USD",
        "card_token": "tok_visa4417a",
        "card_last4": "4417",
    }
    headers = {"Idempotency-Key": "key-1", "X-Request-Id": "req_test"}

    client.post("/v1/charges", json=body, headers=headers)

    assert {e["request_id"] for e in events()} == {"req_test"}


def test_card_token_is_never_logged(charge, caplog):
    caplog.set_level(logging.INFO, logger="payments")

    charge()

    assert "tok_visa4417a" not in caplog.text


def test_sensitive_fields_are_refused(clock):
    with pytest.raises(ValueError):
        EventLogger(clock).info("charge.received", card_token="tok_visa4417a")
