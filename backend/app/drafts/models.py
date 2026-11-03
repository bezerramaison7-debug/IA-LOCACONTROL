"""Automatic drafts of long forms (ADR-024): kept apart from the definitive records.

A draft is the form exactly as typed, stored as opaque JSON. Nothing reads it to move stock,
confirm a contract or issue a document: only the form that saved it reads it back.
"""

import time

from sqlalchemy import JSON, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.base import Base


class FormDraft(Base):
    __tablename__ = "form_drafts"
    __table_args__ = (UniqueConstraint("owner", "kind", "scope"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    # Who typed it: "user:<id>" (and the station once the network edition exists).
    owner: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20))
    # "new" or the id of the record being edited or operated on.
    scope: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSON)
    # Version of the record when the draft was saved; lets the form warn about later changes.
    base_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
