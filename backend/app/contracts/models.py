"""Contracts, renewals chained by base number, physical custody and versioned documents."""

import time

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.masters.models import Editable, Stamp
from app.persistence.base import Base

# VENCENDO and VENCIDO are not stored: they classify ATIVO by due_date and the business date.
STORED_STATUSES = ("RASCUNHO", "AGUARDANDO_RETIRADA", "ATIVO", "ENCERRADO", "CANCELADO")
ORIGINS = ("DIRETO", "ORCAMENTO", "RENOVACAO", "IMPORTADO")
PRICE_OPTIONS = ("ANTERIORES", "ATUAIS", "NEGOCIADOS")
CONDITIONS = ("BOM", "AVARIADO")
UNIT_STATES = ("EM_POSSE", "DEVOLVIDO", "RENOVADO")
DOCUMENT_STATUSES = ("GERADO", "ASSINADO", "SUBSTITUIDO")


def sql_list(values) -> str:
    return "'" + "','".join(values) + "'"


class Contract(Editable, Base):
    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("base_number", "renewal_number"),
        UniqueConstraint("quote_id"),
        CheckConstraint(f"status IN ({sql_list(STORED_STATUSES)})", name="status"),
        CheckConstraint(f"origin IN ({sql_list(ORIGINS)})", name="origin"),
        CheckConstraint(
            f"price_option IS NULL OR price_option IN ({sql_list(PRICE_OPTIONS)})",
            name="price_option",
        ),
        CheckConstraint("base_number > 0 AND renewal_number >= 0", name="numbers"),
        CheckConstraint("total_cents >= 0", name="nonnegative_total"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    # Commercial code is base_number[.renewal_number]; identity is always the internal id.
    base_number: Mapped[int] = mapped_column(Integer)
    renewal_number: Mapped[int] = mapped_column(Integer, default=0)
    root_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    previous_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    customer_snapshot: Mapped[dict] = mapped_column(JSON)
    quote_id: Mapped[int | None] = mapped_column(ForeignKey("quotes.id"))
    origin: Mapped[str] = mapped_column(String(12), default="DIRETO")
    price_option: Mapped[str | None] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(20), default="RASCUNHO", index=True)
    status_reason: Mapped[str] = mapped_column(String(500), default="")
    start_date: Mapped[str] = mapped_column(String(10))
    end_date: Mapped[str] = mapped_column(String(10))
    # Earliest expected return among lines still with the customer; null when nothing is out.
    due_date: Mapped[str | None] = mapped_column(String(10), index=True)
    notes: Mapped[str] = mapped_column(String(2000), default="")
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    items: Mapped[list["ContractItem"]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ContractItem.position",
        foreign_keys="ContractItem.contract_id",
    )

    @property
    def number(self) -> str:
        if self.renewal_number:
            return f"{self.base_number}.{self.renewal_number}"
        return str(self.base_number)

    @property
    def chain_id(self) -> int:
        return self.root_id or self.id


class ContractItem(Base):
    __tablename__ = "contract_items"
    __table_args__ = (
        CheckConstraint("quantity_milli > 0", name="positive_quantity"),
        CheckConstraint("period_count > 0", name="positive_period_count"),
        CheckConstraint("period IN ('DIARIA','SEMANAL','QUINZENAL','MENSAL')", name="period"),
        CheckConstraint("table_price_cents >= 0", name="nonnegative_table_price"),
        CheckConstraint("unit_price_cents >= 0", name="nonnegative_unit_price"),
        CheckConstraint("total_cents >= 0", name="nonnegative_total"),
        CheckConstraint(
            "carried_milli >= 0 AND carried_milli <= quantity_milli", name="carried_range"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    product_code: Mapped[str] = mapped_column(String(40))
    product_name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(2000), default="")
    unit: Mapped[str] = mapped_column(String(20))
    individual_tracking: Mapped[bool] = mapped_column(Boolean, default=False)
    quantity_milli: Mapped[int] = mapped_column(Integer)
    period: Mapped[str] = mapped_column(String(12))
    period_count: Mapped[int] = mapped_column(Integer)
    price_id: Mapped[int | None] = mapped_column(ForeignKey("prices.id"))
    table_price_cents: Mapped[int] = mapped_column(Integer)
    unit_price_cents: Mapped[int] = mapped_column(Integer)
    total_cents: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[str] = mapped_column(String(10))
    end_date: Mapped[str] = mapped_column(String(10))
    # Renewal line: continues this line of the previous contract; the goods never left the
    # customer, so carried_milli enters custody without a new stock movement.
    source_item_id: Mapped[int | None] = mapped_column(ForeignKey("contract_items.id"), index=True)
    carried_milli: Mapped[int] = mapped_column(Integer, default=0)


class ContractEvent(Base):
    __tablename__ = "contract_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    chain_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class ContractTemplate(Base):
    __tablename__ = "contract_templates"
    __table_args__ = (UniqueConstraint("name", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    is_provisional: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class ContractDocument(Base):
    __tablename__ = "contract_documents"
    __table_args__ = (
        UniqueConstraint("contract_id", "version"),
        CheckConstraint(f"status IN ({sql_list(DOCUMENT_STATUSES)})", name="status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("contract_templates.id"))
    version: Mapped[int] = mapped_column(Integer)
    stored_name: Mapped[str] = mapped_column(String(64))
    checksum: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="GERADO")
    reason: Mapped[str] = mapped_column(String(500), default="")
    signed_at: Mapped[int | None] = mapped_column(Integer)
    signed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Withdrawal(Stamp, Base):
    __tablename__ = "withdrawals"
    __table_args__ = (UniqueConstraint("request_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    occurred_on: Mapped[str] = mapped_column(String(10))
    notes: Mapped[str] = mapped_column(String(500), default="")
    request_key: Mapped[str] = mapped_column(String(36))
    items: Mapped[list["WithdrawalItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="WithdrawalItem.id"
    )


class WithdrawalItem(Base):
    __tablename__ = "withdrawal_items"
    __table_args__ = (CheckConstraint("quantity_milli > 0", name="positive_quantity"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    withdrawal_id: Mapped[int] = mapped_column(ForeignKey("withdrawals.id"), index=True)
    contract_item_id: Mapped[int] = mapped_column(ForeignKey("contract_items.id"), index=True)
    quantity_milli: Mapped[int] = mapped_column(Integer)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))


class RentalReturn(Stamp, Base):
    __tablename__ = "returns"
    __table_args__ = (UniqueConstraint("request_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    occurred_on: Mapped[str] = mapped_column(String(10))
    notes: Mapped[str] = mapped_column(String(500), default="")
    request_key: Mapped[str] = mapped_column(String(36))
    items: Mapped[list["ReturnItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="ReturnItem.id"
    )


class ReturnItem(Base):
    __tablename__ = "return_items"
    __table_args__ = (
        CheckConstraint("quantity_milli > 0", name="positive_quantity"),
        CheckConstraint(f"condition IN ({sql_list(CONDITIONS)})", name="condition"),
        CheckConstraint("destination IN ('DISPONIVEL','MANUTENCAO')", name="destination"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    return_id: Mapped[int] = mapped_column(ForeignKey("returns.id"), index=True)
    contract_item_id: Mapped[int] = mapped_column(ForeignKey("contract_items.id"), index=True)
    quantity_milli: Mapped[int] = mapped_column(Integer)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
    condition: Mapped[str] = mapped_column(String(12))
    destination: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str] = mapped_column(String(500), default="")


class ItemUnit(Base):
    """Which physical unit is with the customer under which contract line."""

    __tablename__ = "contract_item_units"
    __table_args__ = (CheckConstraint(f"state IN ({sql_list(UNIT_STATES)})", name="state"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_item_id: Mapped[int] = mapped_column(ForeignKey("contract_items.id"), index=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    state: Mapped[str] = mapped_column(String(12), default="EM_POSSE")
