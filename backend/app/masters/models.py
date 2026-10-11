"""Persistent master data; exact scaled integers, immutable price/stock history."""

import time

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.base import Base

STATES = ("DISPONIVEL", "RESERVADO", "LOCADO", "MANUTENCAO", "INDISPONIVEL", "BAIXADO")
PERIODS = ("DIARIA", "SEMANAL", "QUINZENAL", "MENSAL")
STATE_SQL = "'" + "','".join(STATES) + "'"


class Stamp:
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Editable(Stamp):
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    version: Mapped[int] = mapped_column(Integer, default=1)


class Customer(Editable, Base):
    __tablename__ = "customers"
    __table_args__ = (CheckConstraint("person_type IN ('PF','PJ')", name="person_type"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    person_type: Mapped[str] = mapped_column(String(2))
    legal_name: Mapped[str] = mapped_column(String(160), index=True)
    trade_name: Mapped[str] = mapped_column(String(160), default="")
    document: Mapped[str] = mapped_column(String(14), unique=True)
    state_registration: Mapped[str] = mapped_column(String(30), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    mobile: Mapped[str] = mapped_column(String(30), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    contact: Mapped[str] = mapped_column(String(120), default="")
    notes: Mapped[str] = mapped_column(String(2000), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    addresses: Mapped[list["CustomerAddress"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="CustomerAddress.id"
    )


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    street: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    postal_code: Mapped[str] = mapped_column(String(8))
    label: Mapped[str] = mapped_column(String(60), default="Principal")


class Product(Editable, Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str] = mapped_column(String(2000), default="")
    category: Mapped[str] = mapped_column(String(80), default="")
    unit: Mapped[str] = mapped_column(String(20))
    individual_tracking: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Equipment(Editable, Base):
    __tablename__ = "equipment"
    __table_args__ = (CheckConstraint(f"status IN ({STATE_SQL})", name="status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    product: Mapped[Product] = relationship(lazy="joined")
    code: Mapped[str] = mapped_column(String(40), unique=True)
    asset_tag: Mapped[str | None] = mapped_column(String(80), unique=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), unique=True)
    brand: Mapped[str] = mapped_column(String(80), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20), default="DISPONIVEL")
    notes: Mapped[str] = mapped_column(String(2000), default="")


class StockMovement(Stamp, Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity_milli > 0", name="positive_quantity"),
        CheckConstraint(f"from_status IS NULL OR from_status IN ({STATE_SQL})", name="from_status"),
        CheckConstraint(f"to_status IN ({STATE_SQL})", name="to_status"),
        CheckConstraint("from_status IS NULL OR from_status != to_status", name="distinct_states"),
        UniqueConstraint("request_key"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    product: Mapped[Product] = relationship(lazy="joined")
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    quantity_milli: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(500))
    request_key: Mapped[str | None] = mapped_column(String(36))


class Price(Stamp, Base):
    __tablename__ = "prices"
    __table_args__ = (
        CheckConstraint("amount_cents IS NULL OR amount_cents >= 0", name="nonnegative_amount"),
        CheckConstraint("period IN ('DIARIA','SEMANAL','QUINZENAL','MENSAL')", name="period"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    product: Mapped[Product] = relationship(lazy="joined")
    period: Mapped[str] = mapped_column(String(12))
    effective_date: Mapped[str] = mapped_column(String(10), index=True)
    amount_cents: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(500))
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("prices.id"))
