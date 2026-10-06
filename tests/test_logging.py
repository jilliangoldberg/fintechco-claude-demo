import pytest

from payments.log import EventLogger


def test_request_id_is_echoed(client):
    response = client.get("/healthz", headers={"X-Request-Id": "req_test"})

    assert response.headers["x-request-id"] == "req_test"


def test_sensitive_fields_are_refused(clock):
    with pytest.raises(ValueError):
        EventLogger(clock).info("charge.received", card_token="tok_visa4417a")
