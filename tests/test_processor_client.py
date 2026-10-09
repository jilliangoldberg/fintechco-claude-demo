import httpx
import pytest

from payments.processor.client import HttpProcessorClient, ProcessorDeclined, ProcessorTimeout


def make_client(handler) -> HttpProcessorClient:
    return HttpProcessorClient(
        base_url="https://acquirer.test/v2",
        api_key="test",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )


def charge(client: HttpProcessorClient):
    return client.charge(
        processor_request_id="preq_1",
        amount_minor=4250,
        currency="USD",
        card_token="tok_visa4417a",
        metadata={"customer_id": "cus_1001"},
    )


def test_charge_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Request-Id"] == "preq_1"
        return httpx.Response(200, json={"id": "pch_abc"})

    result = charge(make_client(handler))

    assert result.processor_charge_id == "pch_abc"
    assert result.processor_request_id == "preq_1"


def test_charge_declined():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"decline_code": "insufficient_funds"})

    with pytest.raises(ProcessorDeclined) as exc_info:
        charge(make_client(handler))

    assert exc_info.value.code == "insufficient_funds"


def test_charge_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(ProcessorTimeout) as exc_info:
        charge(make_client(handler))

    assert exc_info.value.elapsed_ms == 10_000
