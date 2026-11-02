"""Customer portal link and renewal requests. A request never creates a renewal by itself."""

import time

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.base import Base

REQUEST_STATUSES = ("PENDENTE", "APROVADA", "RECUSADA", "CANCELADA")


class CustomerUser(Base):
    """One portal account sees exactly one customer."""

    __tablename__ = "customer_users"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class RenewalRequest(Base):
    __tablename__ = "renewal_requests"
    __table_args__ = (
        CheckConstraint("status IN ('PENDENTE','APROVADA','RECUSADA','CANCELADA')", name="status"),
        CheckConstraint("period IN ('DIARIA','SEMANAL','QUINZENAL','MENSAL')", name="period"),
        CheckConstraint("period_count > 0", name="positive_period_count"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    period: Mapped[str] = mapped_column(String(12))
    period_count: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(12), default="PENDENTE", index=True)
    decision_reason: Mapped[str] = mapped_column(String(500), default="")
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
