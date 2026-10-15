import pytest


@pytest.fixture
def charge_id(charge) -> str:
    return charge(amount_minor=5000).json()["id"]


def refund(client, charge_id: str, key: str = "refund-1", **body):
    return client.post(
        f"/v1/charges/{charge_id}/refunds", json=body, headers={"Idempotency-Key": key}
    )


def test_full_refund(client, charge_id):
    response = refund(client, charge_id)

    assert response.status_code == 201
    assert response.json()["amount_minor"] == 5000
    assert client.get(f"/v1/charges/{charge_id}").json()["refunded_minor"] == 5000


def test_partial_refunds_add_up(client, charge_id):
    assert refund(client, charge_id, key="r1", amount_minor=2000).status_code == 201
    assert refund(client, charge_id, key="r2", amount_minor=3000).status_code == 201

    assert client.get(f"/v1/charges/{charge_id}").json()["refunded_minor"] == 5000


def test_refund_cannot_exceed_charge(client, charge_id):
    refund(client, charge_id, key="r1", amount_minor=4000)

    response = refund(client, charge_id, key="r2", amount_minor=2000)

    assert response.status_code == 422
    assert response.json() == {"error": "refund_exceeds_charge", "remaining_minor": 1000}


def test_same_key_replays_refund(client, charge_id, processor):
    first = refund(client, charge_id, amount_minor=1000)
    second = refund(client, charge_id, amount_minor=1000)

    assert second.json() == first.json()
    assert len(processor.refunds) == 1


def test_refund_requires_idempotency_key(client, charge_id):
    response = client.post(f"/v1/charges/{charge_id}/refunds", json={})

    assert response.status_code == 400


def test_refund_unknown_charge_returns_404(client):
    assert refund(client, "ch_missing").status_code == 404


def test_refund_reverses_ledger_entries(client, charge_id, app):
    refund(client, charge_id)

    ledger = app.state.ledger
    assert ledger.unbalanced_transactions() == []
    assert ledger.balance("processor_clearing", "USD") == 0
