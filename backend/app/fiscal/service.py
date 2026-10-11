"""Fiscal document rules. Caller owns a serialized transaction and commit."""

import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import Field, field_validator, model_validator
from sqlalchemy import func, select

from app.auth.service import IdentityService
from app.contracts.models import Contract
from app.fiscal.models import FiscalDocument, FiscalEvent
from app.fiscal.provider import EmissionRequest, ProviderResult, build_provider
from app.masters.models import Customer
from app.masters.schemas import Input, exact_decimal
from app.quotes import calc
from app.quotes.service import CUSTOMER_FIELDS


class FiscalInput(Input):
    customer_id: int = Field(gt=0)
    contract_id: int | None = Field(default=None, gt=0)
    period_start: date
    period_end: date
    amount: Decimal
    description: str = Field(min_length=5, max_length=500)
    request_key: UUID

    @field_validator("amount", mode="before")
    @classmethod
    def amount_value(cls, value):
        result = exact_decimal(value, 2, "999999999.99")
        if result <= 0:
            raise ValueError("Valor deve ser positivo")
        return result

    @model_validator(mode="after")
    def period_order(self):
        if self.period_end < self.period_start:
            raise ValueError("Fim do período anterior ao início")
        return self


class FiscalAction(Input):
    version: int = Field(ge=1)
    reason: str = Field(default="", max_length=500)


def view(row: FiscalDocument, events=None) -> dict:
    data = {
        "id": row.id,
        "customer_id": row.customer_id,
        "customer": row.customer_snapshot,
        "contract_id": row.contract_id,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "amount": calc.money(row.amount_cents),
        "description": row.description,
        "status": row.status,
        "provider": row.provider,
        "environment": row.environment,
        "is_simulation": row.environment == "SIMULACAO",
        "provider_ref": row.provider_ref,
        "number": row.number,
        "series": row.series,
        "access_key": row.access_key,
        "error_message": row.error_message,
        "cancel_reason": row.cancel_reason,
        "has_pdf": row.pdf_name is not None,
        "has_xml": row.xml_name is not None,
        "version": row.version,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "created_by": row.created_by,
    }
    if events is not None:
        data["events"] = [
            {
                "action": e.action,
                "status": e.status,
                "response": e.response,
                "created_at": e.created_at,
                "created_by": e.created_by,
            }
            for e in events
        ]
    return data


class FiscalService:
    def __init__(self, db, actor, settings):
        self.db = db
        self.actor = actor
        self.settings = settings
        self.identity = IdentityService(db, actor)

    def get(self, record_id) -> FiscalDocument:
        row = self.db.get(FiscalDocument, record_id)
        if row is None:
            raise HTTPException(404, "Documento fiscal não encontrado.")
        return row

    def detail(self, record_id) -> dict:
        row = self.get(record_id)
        events = self.db.scalars(
            select(FiscalEvent).where(FiscalEvent.document_id == row.id).order_by(FiscalEvent.id)
        )
        return view(row, list(events))

    def version(self, row, version):
        if row.version != version:
            raise HTTPException(
                409, "Documento alterado por outra operação. Atualize e tente novamente."
            )

    def record(self, row: FiscalDocument, action: str, result: ProviderResult | None, before):
        row.version += 1
        row.updated_at = int(time.time())
        self.db.add(
            FiscalEvent(
                document_id=row.id,
                action=action,
                status=row.status,
                response=result.raw if result else {},
                created_by=self.actor.id,
            )
        )
        self.db.flush()
        self.identity.audit(
            f"fiscal.{action.lower()}",
            "fiscal_documents",
            row.id,
            {"before": before, "after": view(row)},
        )
        self.db.flush()

    def directory(self) -> Path:
        path = Path(self.settings.fiscal_directory)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def provider_for(self, row: FiscalDocument):
        """A document only talks to the provider and environment it was created for."""
        provider = build_provider(self.settings)
        if provider.name != row.provider or provider.environment != row.environment:
            raise HTTPException(
                409,
                "Este documento foi criado em outro provedor ou ambiente fiscal e não pode ser "
                "processado pela configuração atual.",
            )
        return provider

    def create(self, payload) -> dict:
        key = str(payload.request_key)
        existing = self.db.scalar(select(FiscalDocument).where(FiscalDocument.request_key == key))
        if existing:
            same = (
                existing.created_by == self.actor.id
                and existing.customer_id == payload.customer_id
                and existing.contract_id == payload.contract_id
                and existing.period_start == payload.period_start.isoformat()
                and existing.period_end == payload.period_end.isoformat()
                and existing.amount_cents == int(payload.amount * 100)
                and existing.description == payload.description
            )
            if not same:
                raise HTTPException(
                    409, "Identificador de operação já utilizado em outro documento."
                )
            return view(existing)
        customer = self.db.get(Customer, payload.customer_id)
        if customer is None:
            raise HTTPException(404, "Cliente não encontrado.")
        if payload.contract_id is not None:
            contract = self.db.get(Contract, payload.contract_id)
            if contract is None or contract.customer_id != customer.id:
                raise HTTPException(409, "O contrato informado não pertence a este cliente.")
            if contract.status in {"RASCUNHO", "CANCELADO"}:
                raise HTTPException(409, "Contrato em rascunho ou cancelado não pode ser faturado.")
        provider = build_provider(self.settings)
        row = FiscalDocument(
            customer_id=customer.id,
            customer_snapshot={key: getattr(customer, key) for key in CUSTOMER_FIELDS},
            contract_id=payload.contract_id,
            period_start=payload.period_start.isoformat(),
            period_end=payload.period_end.isoformat(),
            amount_cents=int(payload.amount * 100),
            description=payload.description,
            status="PENDENTE",
            provider=provider.name,
            environment=provider.environment,
            request_key=key,
            created_by=self.actor.id,
        )
        self.db.add(row)
        self.db.flush()
        self.record(row, "CREATE", None, None)
        return view(row)

    def apply(self, row: FiscalDocument, result: ProviderResult, provider):
        row.status = result.status
        row.provider_ref = result.provider_ref or row.provider_ref
        row.error_message = result.message if result.status == "ERRO" else ""
        if result.status != "EMITIDO":
            return
        row.number, row.series, row.access_key = result.number, result.series, result.access_key
        folder = self.directory()
        for attribute, extension, fetch in (
            ("pdf_name", "pdf", provider.get_pdf),
            ("xml_name", "xml", provider.get_xml),
        ):
            if getattr(row, attribute) is None:
                name = f"{uuid4().hex}.{extension}"
                (folder / name).write_bytes(fetch(row.provider_ref))
                setattr(row, attribute, name)

    def emit(self, record_id, payload) -> dict:
        row = self.get(record_id)
        self.version(row, payload.version)
        if row.status not in {"PENDENTE", "ERRO"}:
            raise HTTPException(
                409, "Somente documento pendente ou com erro pode ser enviado ao provedor."
            )
        provider = self.provider_for(row)
        contract = self.db.get(Contract, row.contract_id) if row.contract_id else None
        before = view(row)
        result = provider.emit(
            EmissionRequest(
                request_key=row.request_key,
                customer=row.customer_snapshot,
                contract_number=contract.number if contract else None,
                period_start=row.period_start,
                period_end=row.period_end,
                amount_cents=row.amount_cents,
                description=row.description,
            )
        )
        self.apply(row, result, provider)
        self.record(row, "EMIT", result, before)
        return self.detail(row.id)

    def refresh(self, record_id, payload) -> dict:
        row = self.get(record_id)
        self.version(row, payload.version)
        if row.status != "PROCESSANDO":
            raise HTTPException(409, "Somente documento em processamento pode ser consultado.")
        provider = self.provider_for(row)
        before = view(row)
        result = provider.status(row.provider_ref)
        self.apply(row, result, provider)
        self.record(row, "STATUS", result, before)
        return self.detail(row.id)

    def cancel(self, record_id, payload) -> dict:
        row = self.get(record_id)
        self.version(row, payload.version)
        reason = payload.reason.strip()
        if len(reason) < 5:
            raise HTTPException(422, "Informe o motivo com pelo menos 5 caracteres.")
        if row.status not in {"PENDENTE", "ERRO", "EMITIDO"}:
            raise HTTPException(409, "Este documento não pode ser cancelado no estado atual.")
        before = view(row)
        result = None
        if row.status == "EMITIDO":
            result = self.provider_for(row).cancel(row.provider_ref, reason)
            if result.status != "CANCELADO":
                row.error_message = result.message or "O provedor não confirmou o cancelamento."
                self.record(row, "CANCEL", result, before)
                return self.detail(row.id)
        row.status = "CANCELADO"
        row.cancel_reason = reason
        self.record(row, "CANCEL", result, before)
        return self.detail(row.id)

    def file(self, record_id, kind: str) -> tuple[bytes, str, str]:
        row = self.get(record_id)
        name = row.pdf_name if kind == "pdf" else row.xml_name
        if name is None:
            raise HTTPException(404, "Arquivo ainda não disponível para este documento.")
        path = self.directory() / name
        if not path.is_file():
            raise HTTPException(409, "Arquivo do documento não encontrado no armazenamento.")
        media = "application/pdf" if kind == "pdf" else "application/xml"
        label = row.number or str(row.id)
        return path.read_bytes(), f"documento-fiscal-{label}.{kind}", media


def page(db, status=None, customer_id=None, contract_id=None, offset=0, limit=20):
    stmt = select(FiscalDocument)
    if status:
        stmt = stmt.where(FiscalDocument.status == status)
    if customer_id is not None:
        stmt = stmt.where(FiscalDocument.customer_id == customer_id)
    if contract_id is not None:
        stmt = stmt.where(FiscalDocument.contract_id == contract_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(FiscalDocument.id.desc()).offset(offset).limit(limit))
    return {"items": [view(row) for row in rows], "total": total}
