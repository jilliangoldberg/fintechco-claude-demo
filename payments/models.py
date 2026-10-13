"""Request bodies."""

from pydantic import BaseModel, ConfigDict, Field


class ChargeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(pattern=r"^cus_[a-z0-9]+$")
    amount_minor: int = Field(gt=0, le=1_000_000)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    card_token: str = Field(pattern=r"^tok_[A-Za-z0-9]+$")
    card_last4: str = Field(pattern=r"^[0-9]{4}$")
    description: str | None = Field(default=None, max_length=200)

    def fingerprint_fields(self) -> dict:
        """The fields that make two requests 'the same request' for idempotency."""
        return self.model_dump(include={"customer_id", "amount_minor", "currency", "card_token"})


class RefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_minor: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=200)
