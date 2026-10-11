from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.masters.schemas import Input, Note, Period, exact_decimal

Status = Literal[
    "RASCUNHO", "ENVIADO", "APROVADO", "REJEITADO", "EXPIRADO", "CANCELADO", "CONVERTIDO"
]
Action = Literal["send", "approve", "reject", "cancel", "reopen"]


class QuoteItemInput(Input):
    product_id: int = Field(gt=0)
    quantity: Decimal
    period: Period
    period_count: int = Field(ge=1, le=999)
    # None keeps the table price; a different value is a negotiated price (quotes.negotiate).
    unit_price: Decimal | None = None

    @field_validator("quantity", mode="before")
    @classmethod
    def quantity_value(cls, value):
        result = exact_decimal(value, 3, "999999")
        if result <= 0:
            raise ValueError("Quantidade deve ser positiva")
        return result

    @field_validator("unit_price", mode="before")
    @classmethod
    def price_value(cls, value):
        return None if value is None else exact_decimal(value, 2, "999999999.99")


class QuoteInput(Input):
    customer_id: int = Field(gt=0)
    start_date: date
    valid_until: date
    notes: Note = ""
    items: list[QuoteItemInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def distinct_lines(self):
        keys = [(item.product_id, item.period) for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("Produto repetido no mesmo período; some as quantidades")
        return self


class QuoteUpdate(QuoteInput):
    version: int = Field(ge=1)
    # Explicit request to re-read the price table for lines that already had a snapshot.
    refresh_prices: bool = False


class TransitionInput(Input):
    version: int = Field(ge=1)
    reason: str = Field(default="", max_length=500)


class DuplicateInput(Input):
    start_date: date | None = None
    valid_until: date | None = None
