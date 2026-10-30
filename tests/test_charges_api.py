def test_create_charge(charge, processor):
    response = charge()

    assert response.status_code == 201
    body = response.json()
    assert body["object"] == "charge"
    assert body["status"] == "succeeded"
    assert body["amount_minor"] == 4250
    assert body["card_last4"] == "4417"
    assert body["processor_charge_id"] == processor.charges[0].processor_charge_id


def test_missing_idempotency_key_is_rejected(client):
    body = {
        "customer_id": "cus_1001",
        "amount_minor": 4250,
        "currency": "USD",
        "card_token": "tok_visa4417a",
        "card_last4": "4417",
    }

    response = client.post("/v1/charges", json=body)

    assert response.status_code == 400
    assert response.json() == {"error": "idempotency_key_required"}


def test_same_key_replays_original_response(charge, processor):
    first = charge(key="key-1")
    second = charge(key="key-1")

    assert second.status_code == 201
    assert second.json() == first.json()
    assert len(processor.charges) == 1


def test_same_key_with_different_body_is_rejected(charge, processor):
    charge(key="key-1")

    response = charge(key="key-1", amount_minor=999)

    assert response.status_code == 422
    assert response.json() == {"error": "idempotency_key_reused"}
    assert len(processor.charges) == 1


def test_keys_are_scoped_to_customer(charge, processor):
    charge(key="key-1")
    charge(key="key-1", customer_id="cus_2002")

    assert len(processor.charges) == 2


def test_declined_charge_returns_402(charge, processor):
    processor.queue("decline:insufficient_funds")

    response = charge()

    assert response.status_code == 402
    assert response.json() == {"error": "card_declined", "decline_code": "insufficient_funds"}
    assert processor.charges == []


def test_declined_charge_can_retry_with_same_key(charge, processor):
    """SUP-1182: after a soft decline, "Try again" in the app reuses the key."""
    processor.queue("decline:insufficient_funds")
    assert charge(key="key-1").status_code == 402

    retry = charge(key="key-1")

    assert retry.status_code == 201
    assert len(processor.charges) == 1


def test_processor_timeout_returns_504(charge, processor):
    processor.queue("timeout_before_processing")

    response = charge()

    assert response.status_code == 504
    assert response.json()["error"] == "processor_timeout"


def test_unsupported_currency_is_rejected(charge, processor):
    response = charge(currency="XYZ")

    assert response.status_code == 422
    assert processor.requests == []


def test_get_charge(charge, client):
    created = charge().json()

    response = client.get(f"/v1/charges/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_charge_returns_404(client):
    response = client.get("/v1/charges/ch_missing")

    assert response.status_code == 404
    assert response.json() == {"error": "charge_not_found"}


def test_charge_posts_balanced_ledger_entries(charge, app):
    charge()

    ledger = app.state.ledger
    assert ledger.unbalanced_transactions() == []
    assert ledger.balance("processor_clearing", "USD") == 4250
