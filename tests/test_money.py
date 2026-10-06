from decimal import Decimal

import pytest

from payments.money import UnsupportedCurrency, exponent, format_minor, to_minor


def test_exponents():
    assert exponent("USD") == 2
    assert exponent("JPY") == 0


def test_unsupported_currency():
    with pytest.raises(UnsupportedCurrency):
        exponent("XYZ")


def test_to_minor():
    assert to_minor("42.50", "USD") == 4250
    assert to_minor(Decimal("1500"), "JPY") == 1500


def test_to_minor_rounds_half_to_even():
    assert to_minor("10.005", "USD") == 1000
    assert to_minor("10.015", "USD") == 1002


def test_to_minor_rejects_float():
    with pytest.raises(TypeError):
        to_minor(42.5, "USD")


def test_format_minor():
    assert format_minor(4250, "USD") == "42.50 USD"
    assert format_minor(1500, "JPY") == "1500 JPY"
