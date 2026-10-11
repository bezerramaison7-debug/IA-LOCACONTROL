"""Portal rules. Every query is scoped by the customer linked to the signed-in account.

A record of another customer answers 404, never 403: the portal does not confirm that an
identifier exists outside the caller's own data.
"""

import time
from typing import Literal

from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import func, select

from app.auth.models import User
from app.auth.service import IdentityService
from app.contracts.documents import DocumentService
from app.contracts.models import Contract, ContractDocument
from app.contracts.service import ContractService, balance, display_status, quantities
from app.core.clock import business_today
from app.masters.models import Customer
from app.masters.schemas import Input, Period
from app.portal.models import CustomerUser, RenewalRequest
from app.quotes import calc
from app.quotes.models import Quote
from app.quotes.pdf import quote_pdf
from app.quotes.service import effective_status
from app.quotes.service import view as quote_view

HIDDEN_DOCUMENTS = {"SUBSTITUIDO"}
PORTAL_QUOTES = ("ENVIADO", "APROVADO", "REJEITADO", "CONVERTIDO")
ITEM_FIELDS = (
    "product_code",
    "product_name",
    "unit",
    "quantity",
    "period",
    "period_count",
    "unit_price",
    "total",
    "start_date",
    "end_date",
    "withdrawn",
    "returned",
    "outstanding",
)


class LinkInput(Input):
    customer_id: int | None = Field(default=None, gt=0)


class RenewalRequestInput(Input):
    contract_id: int = Field(gt=0)
    period: Period
    period_count: int = Field(ge=1, le=999)
    notes: str = Field(default="", max_length=500)


class DecisionInput(Input):
    decision: Literal["APROVADA", "RECUSADA"]
    reason: str = Field(default="", max_length=500)


def request_view(row: RenewalRequest, contract: Contract, internal=False) -> dict:
    data = {
        "id": row.id,
        "contract_id": row.contract_id,
        "contract_number": contract.number,
        "period": row.period,
        "period_count": row.period_count,
        "notes": row.notes,
        "status": row.status,
        "decision_reason": row.decision_reason,
        "decided_at": row.decided_at,
        "created_at": row.created_at,
    }
    if internal:
        data |= {
            "customer_id": row.customer_id,
            "customer": contract.customer_snapshot["legal_name"],
            "requested_by": row.requested_by,
            "decided_by": row.decided_by,
        }
    return data


class PortalService:
    def __init__(self, db, actor, settings):
        self.db = db
        self.actor = actor
        self.settings = settings
        self.soon_days = settings.contract_due_soon_days
        self.today = business_today()
        link = db.get(CustomerUser, actor.id)
        if link is None:
            raise HTTPException(
                403, "Sua conta ainda não está vinculada a um cliente. Fale com a locadora."
            )
        self.customer_id = link.customer_id

    # ---- scoped lookups ------------------------------------------------------------

    def contract(self, contract_id: int) -> Contract:
        row = self.db.get(Contract, contract_id)
        # Drafts are internal work in progress and stay invisible to the customer.
        if row is None or row.customer_id != self.customer_id or row.status == "RASCUNHO":
            raise HTTPException(404, "Contrato não encontrado.")
        return row

    def contracts(self, status=None) -> list[Contract]:
        stmt = select(Contract).where(
            Contract.customer_id == self.customer_id, Contract.status != "RASCUNHO"
        )
        rows = list(
            self.db.scalars(
                stmt.order_by(Contract.base_number.desc(), Contract.renewal_number.desc())
            )
        )
        if status:
            rows = [r for r in rows if display_status(r, self.today, self.soon_days) == status]
        return rows

    def brief(self, row: Contract) -> dict:
        return {
            "id": row.id,
            "number": row.number,
            "status": display_status(row, self.today, self.soon_days),
            "start_date": row.start_date,
            "end_date": row.end_date,
            "due_date": row.due_date,
            "total": calc.money(row.total_cents),
        }

    # ---- pages ---------------------------------------------------------------------

    def dashboard(self) -> dict:
        active = [row for row in self.contracts() if row.status == "ATIVO"]
        items = [item for row in active for item in row.items]
        moved = quantities(self.db, items)
        rented = sum(balance(item, moved[item.id])["outstanding"] for item in items)
        due = sorted((row for row in active if row.due_date), key=lambda row: row.due_date)
        return {
            "active_contracts": len(active),
            "rented_items": calc.quantity(rented),
            "next_due": [self.brief(row) for row in due[:5]],
            "pending_requests": self.db.scalar(
                select(func.count())
                .select_from(RenewalRequest)
                .where(
                    RenewalRequest.customer_id == self.customer_id,
                    RenewalRequest.status == "PENDENTE",
                )
            ),
        }

    def contract_list(self, status=None) -> dict:
        return {"items": [self.brief(row) for row in self.contracts(status)]}

    def contract_detail(self, contract_id: int) -> dict:
        row = self.contract(contract_id)
        full = ContractService(self.db, self.actor, self.soon_days).view(row)
        return {
            **self.brief(row),
            "origin": full["origin"],
            "items": [
                {
                    **{key: item[key] for key in ITEM_FIELDS},
                    "units": [
                        {"code": unit["code"], "state": unit["state"]} for unit in item["units"]
                    ],
                }
                for item in full["items"]
            ],
            # The chain belongs to the same customer; drafts never appear in it.
            "chain": [c for c in full["chain"] if c["status"] != "RASCUNHO"],
            "events": [
                {"kind": e["kind"], "description": e["description"], "created_at": e["created_at"]}
                for e in full["events"]
            ],
            "documents": [
                {key: d[key] for key in ("id", "version", "status", "created_at", "signed_at")}
                for d in full["documents"]
                if d["status"] not in HIDDEN_DOCUMENTS
            ],
        }

    def equipment(self) -> dict:
        rows = []
        for contract in self.contracts():
            if contract.status != "ATIVO":
                continue
            detail = self.contract_detail(contract.id)
            for item in detail["items"]:
                if item["outstanding"] == "0.000":
                    continue
                held = [unit["code"] for unit in item["units"] if unit["state"] == "EM_POSSE"]
                rows.append(
                    {
                        "contract_id": contract.id,
                        "contract_number": contract.number,
                        "product_code": item["product_code"],
                        "product_name": item["product_name"],
                        "unit": item["unit"],
                        "quantity": item["outstanding"],
                        "units": held,
                        "due_date": item["end_date"],
                    }
                )
        return {"items": rows}

    def documents(self) -> dict:
        rows = self.db.execute(
            select(ContractDocument, Contract)
            .join(Contract, Contract.id == ContractDocument.contract_id)
            .where(
                Contract.customer_id == self.customer_id,
                Contract.status != "RASCUNHO",
                ContractDocument.status.notin_(HIDDEN_DOCUMENTS),
            )
            .order_by(ContractDocument.id.desc())
        )
        return {
            "items": [
                {
                    "id": document.id,
                    "contract_id": contract.id,
                    "contract_number": contract.number,
                    "version": document.version,
                    "status": document.status,
                    "created_at": document.created_at,
                    "signed_at": document.signed_at,
                }
                for document, contract in rows
            ]
        }

    def download(self, document_id: int) -> tuple[bytes, str]:
        document = self.db.get(ContractDocument, document_id)
        if document is None or document.status in HIDDEN_DOCUMENTS:
            raise HTTPException(404, "Documento não encontrado.")
        self.contract(document.contract_id)  # 404 unless it is the caller's own contract
        return DocumentService(self.db, self.actor, self.settings).download(document_id)

    def quote(self, quote_id: int) -> Quote:
        row = self.db.get(Quote, quote_id)
        if row is None or row.customer_id != self.customer_id or row.status not in PORTAL_QUOTES:
            raise HTTPException(404, "Orçamento não encontrado.")
        return row

    def quote_brief(self, row: Quote) -> dict:
        return {
            "id": row.id,
            "number": row.number,
            "status": effective_status(row, self.today),
            "start_date": row.start_date,
            "valid_until": row.valid_until,
            "total": calc.money(row.total_cents),
        }

    def quotes(self) -> dict:
        rows = self.db.scalars(
            select(Quote)
            .where(Quote.customer_id == self.customer_id, Quote.status.in_(PORTAL_QUOTES))
            .order_by(Quote.id.desc())
        )
        return {"items": [self.quote_brief(row) for row in rows]}

    def quote_detail(self, quote_id: int) -> dict:
        row = self.quote(quote_id)
        full = quote_view(row, self.today)
        return {
            **self.quote_brief(row),
            "items": [
                {
                    key: item[key]
                    for key in (
                        "product_code",
                        "product_name",
                        "unit",
                        "quantity",
                        "period",
                        "period_count",
                        "unit_price",
                        "total",
                        "end_date",
                    )
                }
                for item in full["items"]
            ],
        }

    def quote_pdf(self, quote_id: int) -> tuple[bytes, str]:
        row = self.quote(quote_id)
        return quote_pdf(quote_view(row, self.today), self.settings), f"{row.number}.pdf"

    def profile(self) -> dict:
        customer = self.db.get(Customer, self.customer_id)
        fields = (
            "person_type",
            "legal_name",
            "trade_name",
            "document",
            "state_registration",
            "phone",
            "mobile",
            "email",
            "contact",
        )
        return {
            **{key: getattr(customer, key) for key in fields},
            "addresses": [
                {
                    key: getattr(a, key)
                    for key in ("label", "street", "city", "state", "postal_code")
                }
                for a in customer.addresses
            ],
        }

    # ---- renewal requests ----------------------------------------------------------

    def requests(self) -> dict:
        rows = self.db.execute(
            select(RenewalRequest, Contract)
            .join(Contract, Contract.id == RenewalRequest.contract_id)
            .where(RenewalRequest.customer_id == self.customer_id)
            .order_by(RenewalRequest.id.desc())
        )
        return {"items": [request_view(row, contract) for row, contract in rows]}

    def request_renewal(self, payload) -> dict:
        contract = self.contract(payload.contract_id)
        if contract.status != "ATIVO":
            raise HTTPException(409, "Somente contrato ativo pode ter renovação solicitada.")
        pending = self.db.scalar(
            select(RenewalRequest.id).where(
                RenewalRequest.contract_id == contract.id, RenewalRequest.status == "PENDENTE"
            )
        )
        if pending:
            raise HTTPException(409, "Já existe uma solicitação em análise para este contrato.")
        row = RenewalRequest(
            contract_id=contract.id,
            customer_id=self.customer_id,
            requested_by=self.actor.id,
            period=payload.period,
            period_count=payload.period_count,
            notes=payload.notes,
        )
        self.db.add(row)
        self.db.flush()
        IdentityService(self.db, self.actor).audit(
            "renewal_request.created", "renewal_requests", row.id, request_view(row, contract)
        )
        self.db.flush()
        return request_view(row, contract)

    def cancel_request(self, request_id: int) -> dict:
        row = self.db.get(RenewalRequest, request_id)
        if row is None or row.customer_id != self.customer_id:
            raise HTTPException(404, "Solicitação não encontrada.")
        if row.status != "PENDENTE":
            raise HTTPException(409, "Somente solicitação em análise pode ser cancelada.")
        row.status = "CANCELADA"
        row.decided_at = int(time.time())
        contract = self.db.get(Contract, row.contract_id)
        IdentityService(self.db, self.actor).audit(
            "renewal_request.cancelled", "renewal_requests", row.id, request_view(row, contract)
        )
        self.db.flush()
        return request_view(row, contract)


class PortalAdmin:
    """Internal side: link accounts to customers and decide renewal requests."""

    def __init__(self, db, actor):
        self.db = db
        self.actor = actor
        self.identity = IdentityService(db, actor)

    def link_view(self, user_id: int) -> dict:
        link = self.db.get(CustomerUser, user_id)
        customer = self.db.get(Customer, link.customer_id) if link else None
        return {
            "user_id": user_id,
            "customer_id": customer.id if customer else None,
            "customer": customer.legal_name if customer else None,
        }

    def link(self, user_id: int, payload) -> dict:
        user = self.db.get(User, user_id)
        if user is None:
            raise HTTPException(404, "Usuário não encontrado.")
        if {role.code for role in user.roles} != {"CLIENTE"}:
            raise HTTPException(409, "Somente usuário com perfil Cliente pode ser vinculado.")
        before = self.link_view(user_id)
        link = self.db.get(CustomerUser, user_id)
        if payload.customer_id is None:
            if link:
                self.db.delete(link)
        else:
            customer = self.db.get(Customer, payload.customer_id)
            if customer is None:
                raise HTTPException(404, "Cliente não encontrado.")
            if link:
                link.customer_id = customer.id
                link.created_by = self.actor.id
            else:
                self.db.add(
                    CustomerUser(user_id=user_id, customer_id=customer.id, created_by=self.actor.id)
                )
        self.db.flush()
        # A different customer must never be reachable through an old session.
        self.identity.revoke(user_id)
        after = self.link_view(user_id)
        self.identity.audit(
            "portal.link_changed", "users", user_id, {"before": before, "after": after}
        )
        self.db.flush()
        return after

    def requests(self, status=None, offset=0, limit=20) -> dict:
        stmt = select(RenewalRequest, Contract).join(
            Contract, Contract.id == RenewalRequest.contract_id
        )
        if status:
            stmt = stmt.where(RenewalRequest.status == status)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = self.db.execute(stmt.order_by(RenewalRequest.id.desc()).offset(offset).limit(limit))
        return {
            "items": [request_view(row, contract, internal=True) for row, contract in rows],
            "total": total,
        }

    def decide(self, request_id: int, payload) -> dict:
        row = self.db.get(RenewalRequest, request_id)
        if row is None:
            raise HTTPException(404, "Solicitação não encontrada.")
        if row.status != "PENDENTE":
            raise HTTPException(409, "Esta solicitação já foi decidida.")
        reason = payload.reason.strip()
        if payload.decision == "RECUSADA" and len(reason) < 5:
            raise HTTPException(422, "Informe o motivo da recusa com pelo menos 5 caracteres.")
        contract = self.db.get(Contract, row.contract_id)
        before = request_view(row, contract, internal=True)
        # Approval records the decision only; the employee performs the renewal itself.
        row.status = payload.decision
        row.decision_reason = reason
        row.decided_by = self.actor.id
        row.decided_at = int(time.time())
        after = request_view(row, contract, internal=True)
        self.identity.audit(
            "renewal_request.decided",
            "renewal_requests",
            row.id,
            {"before": before, "after": after},
        )
        self.db.flush()
        return after
