import pytest

from payments.db import connect
from payments.ids import SequentialIds
from payments.services.ledger import (
    CUSTOMER_PAYMENTS,
    PROCESSOR_CLEARING,
    Entry,
    Ledger,
    UnbalancedTransaction,
)


@pytest.fixture
def ledger(clock) -> Ledger:
    return Ledger(connect(":memory:"), SequentialIds(), clock)


def test_charge_posts_balanced_entries(ledger):
    ledger.post_charge("ch_1", 4250, "USD")

    assert ledger.unbalanced_transactions() == []
    assert ledger.balance(PROCESSOR_CLEARING, "USD") == 4250
    assert ledger.balance(CUSTOMER_PAYMENTS, "USD") == -4250


def test_refund_reverses_charge(ledger):
    ledger.post_charge("ch_1", 4250, "USD")
    ledger.post_refund("re_1", 4250, "USD")

    assert ledger.balance(PROCESSOR_CLEARING, "USD") == 0
    assert ledger.balance(CUSTOMER_PAYMENTS, "USD") == 0


def test_unbalanced_transaction_is_rejected(ledger):
    with pytest.raises(UnbalancedTransaction):
        ledger.post(
            "ch_1",
            [
                Entry(PROCESSOR_CLEARING, "debit", 4250, "USD"),
                Entry(CUSTOMER_PAYMENTS, "credit", 4200, "USD"),
            ],
        )


def test_amounts_must_be_positive(ledger):
    with pytest.raises(ValueError):
        ledger.post_charge("ch_1", 0, "USD")
