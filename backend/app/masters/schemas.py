import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

State = Literal["DISPONIVEL", "RESERVADO", "LOCADO", "MANUTENCAO", "INDISPONIVEL", "BAIXADO"]
Period = Literal["DIARIA", "SEMANAL", "QUINZENAL", "MENSAL"]
Short = Annotated[str, Field(max_length=160)]
Code = Annotated[str, Field(min_length=1, max_length=40, pattern=r"^[A-Z0-9][A-Z0-9._/-]*$")]
Note = Annotated[str, Field(max_length=2000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Address(Input):
    label: str = Field(default="Principal", min_length=1, max_length=60)
    street: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(pattern=r"^[A-Z]{2}$")
    postal_code: str = Field(pattern=r"^\d{8}$")

    @field_validator("postal_code", mode="before")
    @classmethod
    def normalize_postal(cls, value):
        return value.replace("-", "").replace(" ", "") if isinstance(value, str) else value


class CustomerInput(Input):
    person_type: Literal["PF", "PJ"]
    legal_name: str = Field(min_length=2, max_length=160)
    trade_name: Short = ""
    document: str = Field(min_length=11, max_length=14)
    state_registration: str = Field(default="", max_length=30)
    phone: str = Field(default="", max_length=30)
    mobile: str = Field(default="", max_length=30)
    email: str = Field(default="", max_length=254)
    contact: str = Field(default="", max_length=120)
    notes: Note = ""
    is_active: bool = True
    addresses: list[Address] = Field(default_factory=list, max_length=10)

    @field_validator("document", mode="before")
    @classmethod
    def normalize_document(cls, value):
        return re.sub(r"[.\s/-]", "", value).upper() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def email_format(cls, value):
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("E-mail inválido")
        return value.lower()

    @model_validator(mode="after")
    def document_format(self):
        pattern = r"[0-9]{11}" if self.person_type == "PF" else r"[A-Z0-9]{12}[0-9]{2}"
        if not re.fullmatch(pattern, self.document):
            raise ValueError("Documento incompatível com PF/PJ")
        return self


class CustomerUpdate(CustomerInput):
    version: int = Field(ge=1)


class ProductInput(Input):
    code: Code
    name: str = Field(min_length=2, max_length=160)
    description: Note = ""
    category: str = Field(default="", max_length=80)
    unit: str = Field(min_length=1, max_length=20)
    individual_tracking: bool = False
    is_active: bool = True

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class ProductUpdate(ProductInput):
    version: int = Field(ge=1)


class EquipmentInput(Input):
    product_id: int = Field(gt=0)
    code: Code
    asset_tag: str | None = Field(default=None, max_length=80)
    serial_number: str | None = Field(default=None, max_length=100)
    brand: str = Field(default="", max_length=80)
    model: str = Field(default="", max_length=100)
    notes: Note = ""

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("asset_tag", "serial_number", mode="before")
    @classmethod
    def normalize_optional(cls, value):
        return value.strip().upper() or None if isinstance(value, str) else value


class EquipmentUpdate(EquipmentInput):
    version: int = Field(ge=1)


class EquipmentStatus(Input):
    version: int = Field(ge=1)
    status: State
    reason: str = Field(min_length=5, max_length=500)


def exact_decimal(value, places, maximum):
    # JSON decimal strings are intentional; binary floating point is never accepted.
    if not isinstance(value, str) or not re.fullmatch(r"\d+(\.\d{1," + str(places) + r"})?", value):
        raise ValueError("Use texto decimal com ponto e precisão permitida")
    result = Decimal(value)
    if result > Decimal(maximum):
        raise ValueError("Valor excede o limite")
    return result


class MovementInput(Input):
    product_id: int = Field(gt=0)
    from_status: State | None = None
    to_status: State
    quantity: Decimal
    reason: str = Field(min_length=5, max_length=500)
    request_key: UUID

    @field_validator("quantity", mode="before")
    @classmethod
    def quantity_value(cls, value):
        result = exact_decimal(value, 3, "999999999")
        if result <= 0:
            raise ValueError("Quantidade deve ser positiva")
        return result


class PriceInput(Input):
    product_id: int = Field(gt=0)
    period: Period
    effective_date: date
    amount: Decimal
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("amount", mode="before")
    @classmethod
    def amount_value(cls, value):
        return exact_decimal(value, 2, "999999999.99")


class PriceRetire(Input):
    reason: str = Field(min_length=5, max_length=500)
