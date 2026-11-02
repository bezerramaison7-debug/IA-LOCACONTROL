from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.masters.schemas import Input, Note, Period, exact_decimal
from app.quotes.calc import business_date
from app.quotes.schemas import QuoteItemInput

Status = Literal[
    "RASCUNHO", "AGUARDANDO_RETIRADA", "ATIVO", "VENCENDO", "VENCIDO", "ENCERRADO", "CANCELADO"
]
PriceOption = Literal["ANTERIORES", "ATUAIS", "NEGOCIADOS"]
Origin = Literal["DIRETO", "ORCAMENTO", "RENOVACAO", "IMPORTADO"]
Reason = Field(default="", max_length=500)


def positive(value):
    result = exact_decimal(value, 3, "999999")
    if result <= 0:
        raise ValueError("Quantidade deve ser positiva")
    return result


def distinct(values, message):
    if len(values) != len(set(values)):
        raise ValueError(message)


class ContractInput(Input):
    customer_id: int = Field(gt=0)
    start_date: date
    notes: Note = ""
    items: list[QuoteItemInput] = Field(min_length=1, max_length=100)

    _dates = field_validator("start_date")(business_date)

    @model_validator(mode="after")
    def distinct_lines(self):
        distinct(
            [(item.product_id, item.period) for item in self.items],
            "Produto repetido no mesmo período; some as quantidades",
        )
        return self


class ContractUpdate(ContractInput):
    version: int = Field(ge=1)
    refresh_prices: bool = False


class ActionInput(Input):
    version: int = Field(ge=1)
    reason: str = Reason


class NumberingInput(Input):
    next_number: int = Field(ge=1, le=999_999_999)


class WithdrawLine(Input):
    contract_item_id: int = Field(gt=0)
    quantity: Decimal
    equipment_ids: list[int] = Field(default_factory=list, max_length=500)

    _quantity = field_validator("quantity", mode="before")(positive)


class WithdrawInput(Input):
    occurred_on: date
    notes: str = Reason
    request_key: UUID
    items: list[WithdrawLine] = Field(min_length=1, max_length=100)

    _dates = field_validator("occurred_on")(business_date)

    @model_validator(mode="after")
    def distinct_lines(self):
        distinct([line.contract_item_id for line in self.items], "Item repetido na retirada")
        distinct([e for line in self.items for e in line.equipment_ids], "Equipamento repetido")
        return self


class ReturnLine(Input):
    contract_item_id: int = Field(gt=0)
    quantity: Decimal
    # Required for individually tracked products: one line per physical unit.
    equipment_id: int | None = None
    condition: Literal["BOM", "AVARIADO"]
    destination: Literal["DISPONIVEL", "MANUTENCAO"] | None = None
    notes: str = Reason

    _quantity = field_validator("quantity", mode="before")(positive)

    @model_validator(mode="after")
    def damaged_goes_to_maintenance(self):
        if self.destination is None:
            self.destination = "DISPONIVEL" if self.condition == "BOM" else "MANUTENCAO"
        if self.condition == "AVARIADO" and self.destination != "MANUTENCAO":
            raise ValueError("Item avariado deve seguir para manutenção")
        return self


class ReturnInput(Input):
    occurred_on: date
    notes: str = Reason
    request_key: UUID
    items: list[ReturnLine] = Field(min_length=1, max_length=500)

    _dates = field_validator("occurred_on")(business_date)

    @model_validator(mode="after")
    def distinct_units(self):
        distinct(
            [line.equipment_id for line in self.items if line.equipment_id is not None],
            "Equipamento repetido na devolução",
        )
        return self


class RenewLine(Input):
    source_item_id: int = Field(gt=0)
    quantity: Decimal
    period: Period
    period_count: int = Field(ge=1, le=999)
    unit_price: Decimal | None = None
    equipment_ids: list[int] = Field(default_factory=list, max_length=500)

    _quantity = field_validator("quantity", mode="before")(positive)

    @field_validator("equipment_ids")
    @classmethod
    def distinct_units(cls, value):
        distinct(value, "Equipamento repetido na renovação")
        return value

    @field_validator("unit_price", mode="before")
    @classmethod
    def price_value(cls, value):
        return None if value is None else exact_decimal(value, 2, "999999999.99")


class RenewInput(Input):
    version: int = Field(ge=1)
    start_date: date
    price_option: PriceOption
    notes: Note = ""
    items: list[RenewLine] = Field(min_length=1, max_length=100)

    _dates = field_validator("start_date")(business_date)

    @model_validator(mode="after")
    def distinct_lines(self):
        distinct([line.source_item_id for line in self.items], "Item repetido na renovação")
        return self


class TemplateInput(Input):
    name: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=20, max_length=60_000)
    is_provisional: bool = False


class GenerateInput(Input):
    template_id: int | None = Field(default=None, gt=0)
    reason: str = Reason


class SignInput(Input):
    notes: str = Reason
