from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Mapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sheet: str = Field(min_length=1, max_length=255)
    header_row: int = Field(ge=1, le=10001)
    entity: Literal["customers", "products", "equipment", "prices", "stock"]
    columns: dict[str, int] = Field(min_length=1, max_length=30)
    decimal_separator: Literal[",", "."] = ","
    date_format: Literal["DMY", "ISO"] = "DMY"


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mapping: Mapping
    preview_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirm: Literal[True]
