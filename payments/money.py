"""Money helpers. Amounts are always integers in the currency's minor unit."""

from decimal import ROUND_HALF_EVEN, Decimal

CURRENCY_EXPONENTS = {"USD": 2, "EUR": 2, "GBP": 2, "CAD": 2, "JPY": 0}


class UnsupportedCurrency(ValueError):
    pass


def exponent(currency: str) -> int:
    try:
        return CURRENCY_EXPONENTS[currency]
    except KeyError:
        raise UnsupportedCurrency(currency) from None


def to_minor(amount: Decimal | str | int, currency: str) -> int:
    """Convert a major-unit amount to minor units, rounding half to even."""
    if isinstance(amount, float):
        raise TypeError("use Decimal or str for money, not float")
    scale = Decimal(10) ** exponent(currency)
    return int((Decimal(amount) * scale).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def format_minor(amount_minor: int, currency: str) -> str:
    """Human-readable amount, e.g. ``format_minor(4250, "USD") == "42.50 USD"``."""
    places = exponent(currency)
    return f"{Decimal(amount_minor).scaleb(-places):.{places}f} {currency}"
