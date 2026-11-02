"""Quotes keep price and customer snapshots; later table changes never rewrite them."""

import time

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.masters.models import Editable
from app.persistence.base import Base

# EXPIRADO is not stored: it is ENVIADO whose valid_until is before the business date.
STORED_STATUSES = ("RASCUNHO", "ENVIADO", "APROVADO", "REJEITADO", "CANCELADO", "CONVERTIDO")
STATUS_SQL = "'" + "','".join(STORED_STATUSES) + "'"


class Quote(Editable, Base):
    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("year", "sequence"),
        CheckConstraint(f"status IN ({STATUS_SQL})", name="status"),
        CheckConstraint("sequence > 0", name="positive_sequence"),
        CheckConstraint("total_cents >= 0", name="nonnegative_total"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    sequence: Mapped[int] = mapped_column(Integer)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    customer_snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(12), default="RASCUNHO", index=True)
    status_reason: Mapped[str] = mapped_column(String(500), default="")
    start_date: Mapped[str] = mapped_column(String(10))
    valid_until: Mapped[str] = mapped_column(String(10))
    notes: Mapped[str] = mapped_column(String(2000), default="")
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    duplicated_from_id: Mapped[int | None] = mapped_column(ForeignKey("quotes.id"))
    items: Mapped[list["QuoteItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="QuoteItem.position"
    )
    transitions: Mapped[list["QuoteTransition"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="QuoteTransition.id"
    )

    @property
    def number(self) -> str:
        return f"ORC-{self.year}-{self.sequence:06d}"


class QuoteItem(Base):
    __tablename__ = "quote_items"
    __table_args__ = (
        CheckConstraint("quantity_milli > 0", name="positive_quantity"),
        CheckConstraint("period_count > 0", name="positive_period_count"),
        CheckConstraint("period IN ('DIARIA','SEMANAL','QUINZENAL','MENSAL')", name="period"),
        CheckConstraint("table_price_cents >= 0", name="nonnegative_table_price"),
        CheckConstraint("unit_price_cents >= 0", name="nonnegative_unit_price"),
        CheckConstraint("total_cents >= 0", name="nonnegative_total"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    product_code: Mapped[str] = mapped_column(String(40))
    product_name: Mapped[str] = mapped_column(String(160))
    unit: Mapped[str] = mapped_column(String(20))
    quantity_milli: Mapped[int] = mapped_column(Integer)
    period: Mapped[str] = mapped_column(String(12))
    period_count: Mapped[int] = mapped_column(Integer)
    price_id: Mapped[int | None] = mapped_column(ForeignKey("prices.id"))
    table_price_cents: Mapped[int] = mapped_column(Integer)
    unit_price_cents: Mapped[int] = mapped_column(Integer)
    total_cents: Mapped[int] = mapped_column(Integer)
    end_date: Mapped[str] = mapped_column(String(10))


class QuoteTransition(Base):
    __tablename__ = "quote_transitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(12))
    to_status: Mapped[str] = mapped_column(String(12))
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
