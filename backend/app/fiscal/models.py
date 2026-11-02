"""Fiscal documents and the trail of every provider call."""

import time

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.masters.models import Editable
from app.persistence.base import Base

STATUSES = ("PENDENTE", "PROCESSANDO", "EMITIDO", "ERRO", "CANCELADO")


class FiscalDocument(Editable, Base):
    __tablename__ = "fiscal_documents"
    __table_args__ = (
        UniqueConstraint("request_key"),
        CheckConstraint(
            "status IN ('PENDENTE','PROCESSANDO','EMITIDO','ERRO','CANCELADO')", name="status"
        ),
        CheckConstraint("amount_cents > 0", name="positive_amount"),
        CheckConstraint("period_end >= period_start", name="period_order"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    customer_snapshot: Mapped[dict] = mapped_column(JSON)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    period_start: Mapped[str] = mapped_column(String(10))
    period_end: Mapped[str] = mapped_column(String(10))
    amount_cents: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(12), default="PENDENTE", index=True)
    # Which adapter and environment produced the returns below; a simulation is never fiscal.
    provider: Mapped[str] = mapped_column(String(40))
    environment: Mapped[str] = mapped_column(String(12))
    # Sent to the provider on every attempt so a retry can never issue a second document.
    request_key: Mapped[str] = mapped_column(String(36))
    provider_ref: Mapped[str | None] = mapped_column(String(120))
    number: Mapped[str | None] = mapped_column(String(40))
    series: Mapped[str | None] = mapped_column(String(20))
    access_key: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str] = mapped_column(String(500), default="")
    cancel_reason: Mapped[str] = mapped_column(String(500), default="")
    pdf_name: Mapped[str | None] = mapped_column(String(64))
    xml_name: Mapped[str | None] = mapped_column(String(64))


class FiscalEvent(Base):
    __tablename__ = "fiscal_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("fiscal_documents.id"), index=True)
    action: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(12))
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
