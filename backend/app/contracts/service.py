"""Contract rules. Caller owns a serialized transaction and commit."""

import re
import time
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select

from app.auth.catalog import permission_codes
from app.auth.service import IdentityService
from app.contracts.models import (
    AppSetting,
    Contract,
    ContractDocument,
    ContractEvent,
    ContractItem,
    ItemUnit,
    RentalReturn,
    ReturnItem,
    Withdrawal,
    WithdrawalItem,
)
from app.core.clock import business_today
from app.masters.models import Customer, Equipment, Product
from app.quotes import calc
from app.quotes.models import Quote, QuoteTransition
from app.quotes.service import QuoteService, effective_status
from app.quotes.service import view as quote_view

NUMBERING_KEY = "contracts.next_number"
STATUS_LABELS = {
    "RASCUNHO": "em rascunho",
    "AGUARDANDO_RETIRADA": "aguardando retirada",
    "ATIVO": "ativo",
    "VENCENDO": "vencendo",
    "VENCIDO": "vencido",
    "ENCERRADO": "encerrado",
    "CANCELADO": "cancelado",
}


def display_status(row: Contract, today: date, soon_days: int) -> str:
    if row.status == "ATIVO" and row.due_date:
        if row.due_date < today.isoformat():
            return "VENCIDO"
        if row.due_date <= (today + timedelta(days=soon_days)).isoformat():
            return "VENCENDO"
    return row.status


def quantities(db, items) -> dict:
    """Per contract line: what left the stock, what came back and what a renewal took over."""
    ids = [item.id for item in items]
    result = {item_id: {"withdrawn": 0, "returned": 0, "renewed": 0} for item_id in ids}
    if not ids:
        return result
    sources = (
        ("withdrawn", WithdrawalItem.contract_item_id, WithdrawalItem.quantity_milli),
        ("returned", ReturnItem.contract_item_id, ReturnItem.quantity_milli),
        ("renewed", ContractItem.source_item_id, ContractItem.carried_milli),
    )
    for key, column, amount in sources:
        for item_id, total in db.execute(
            select(column, func.sum(amount)).where(column.in_(ids)).group_by(column)
        ):
            result[item_id][key] = total or 0
    return result


def balance(item: ContractItem, moved: dict) -> dict:
    """outstanding = with the customer now; to_withdraw = contracted but not yet picked up."""
    return {
        **moved,
        "outstanding": moved["withdrawn"]
        + item.carried_milli
        - moved["returned"]
        - moved["renewed"],
        "to_withdraw": item.quantity_milli - item.carried_milli - moved["withdrawn"],
    }


def summary(row: Contract, today: date, soon_days: int) -> dict:
    return {
        "id": row.id,
        "number": row.number,
        "base_number": row.base_number,
        "renewal_number": row.renewal_number,
        "chain_id": row.chain_id,
        "previous_id": row.previous_id,
        "customer_id": row.customer_id,
        "customer": row.customer_snapshot,
        "quote_id": row.quote_id,
        "origin": row.origin,
        "price_option": row.price_option,
        "status": display_status(row, today, soon_days),
        "stored_status": row.status,
        "status_reason": row.status_reason,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "due_date": row.due_date,
        "notes": row.notes,
        "total": calc.money(row.total_cents),
        "item_count": len(row.items),
        "version": row.version,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "created_by": row.created_by,
    }


class ContractService:
    def __init__(self, db, actor, soon_days: int = 3):
        self.db = db
        self.actor = actor
        self.soon_days = soon_days
        self.identity = IdentityService(db, actor)
        # Quote pricing rules are reused; the negotiation right is the contract one.
        self.pricing = QuoteService(db, actor)
        self.pricing.can_negotiate = "contracts.negotiate" in permission_codes(actor)

    # ---- reading -------------------------------------------------------------------

    def get(self, record_id) -> Contract:
        row = self.db.get(Contract, record_id)
        if row is None:
            raise HTTPException(404, "Contrato não encontrado.")
        return row

    def item_view(self, item: ContractItem, moved: dict, units: list) -> dict:
        numbers = balance(item, moved)
        return {
            "id": item.id,
            "position": item.position,
            "product_id": item.product_id,
            "product_code": item.product_code,
            "product_name": item.product_name,
            "description": item.description,
            "unit": item.unit,
            "individual_tracking": item.individual_tracking,
            "quantity": calc.quantity(item.quantity_milli),
            "period": item.period,
            "period_count": item.period_count,
            "table_price": calc.money(item.table_price_cents),
            "unit_price": calc.money(item.unit_price_cents),
            "negotiated": item.unit_price_cents != item.table_price_cents,
            "discount": format((item.table_price_cents - item.unit_price_cents) / 100, ".2f"),
            "total": calc.money(item.total_cents),
            "start_date": item.start_date,
            "end_date": item.end_date,
            "source_item_id": item.source_item_id,
            **{key: calc.quantity(value) for key, value in numbers.items()},
            "units": units,
        }

    def detail(self, record_id) -> dict:
        return self.view(self.get(record_id))

    def view(self, row: Contract) -> dict:
        today = business_today()
        moved = quantities(self.db, row.items)
        item_ids = [item.id for item in row.items]
        units = {item_id: [] for item_id in item_ids}
        if item_ids:
            for unit, code in self.db.execute(
                select(ItemUnit, Equipment.code)
                .join(Equipment, Equipment.id == ItemUnit.equipment_id)
                .where(ItemUnit.contract_item_id.in_(item_ids))
                .order_by(ItemUnit.id)
            ):
                units[unit.contract_item_id].append(
                    {"equipment_id": unit.equipment_id, "code": code, "state": unit.state}
                )
        table_total = sum(
            calc.item_total_cents(i.quantity_milli, i.table_price_cents, i.period_count)
            for i in row.items
        )
        chain = self.db.scalars(
            select(Contract)
            .where(or_(Contract.id == row.chain_id, Contract.root_id == row.chain_id))
            .order_by(Contract.renewal_number)
        )
        events = self.db.scalars(
            select(ContractEvent)
            .where(ContractEvent.chain_id == row.chain_id)
            .order_by(ContractEvent.id)
        )
        documents = self.db.scalars(
            select(ContractDocument)
            .where(ContractDocument.contract_id == row.id)
            .order_by(ContractDocument.version.desc())
        )
        quote = self.db.get(Quote, row.quote_id) if row.quote_id else None
        return {
            **summary(row, today, self.soon_days),
            "quote_number": quote.number if quote else None,
            "table_total": calc.money(table_total),
            "negotiated_difference": format((table_total - row.total_cents) / 100, ".2f"),
            "items": [self.item_view(i, moved[i.id], units[i.id]) for i in row.items],
            "chain": [
                {
                    "id": c.id,
                    "number": c.number,
                    "status": display_status(c, today, self.soon_days),
                    "start_date": c.start_date,
                    "end_date": c.end_date,
                    "total": calc.money(c.total_cents),
                }
                for c in chain
            ],
            "events": [
                {
                    "id": e.id,
                    "contract_id": e.contract_id,
                    "kind": e.kind,
                    "description": e.description,
                    "created_at": e.created_at,
                    "created_by": e.created_by,
                }
                for e in events
            ],
            "documents": [document_view(d) for d in documents],
            "withdrawals": [
                movement_view(w)
                for w in self.db.scalars(
                    select(Withdrawal)
                    .where(Withdrawal.contract_id == row.id)
                    .order_by(Withdrawal.id)
                )
            ],
            "returns": [
                movement_view(r)
                for r in self.db.scalars(
                    select(RentalReturn)
                    .where(RentalReturn.contract_id == row.id)
                    .order_by(RentalReturn.id)
                )
            ],
        }

    # ---- shared helpers ------------------------------------------------------------

    def version(self, row, version):
        if row.version != version:
            raise HTTPException(
                409, "Contrato alterado por outra operação. Atualize e tente novamente."
            )

    def touch(self, row):
        row.version += 1
        row.updated_at = int(time.time())

    def event(self, row: Contract, kind: str, description: str):
        self.db.add(
            ContractEvent(
                contract_id=row.id,
                chain_id=row.chain_id,
                kind=kind,
                description=description[:500],
                created_by=self.actor.id,
            )
        )

    def audit(self, action, row, before=None):
        self.db.flush()
        after = self.view(row)
        # The chain and the timeline are context, not state of this record.
        for key in ("chain", "events"):
            after.pop(key)
            if before:
                before.pop(key, None)
        self.identity.audit(action, "contracts", row.id, {"before": before, "after": after})
        # Audit failure must fail the entire operation, before any response is sent.
        self.db.flush()

    def reason(self, payload) -> str:
        reason = payload.reason.strip()
        if len(reason) < 5:
            raise HTTPException(422, "Informe o motivo com pelo menos 5 caracteres.")
        return reason

    def refresh_state(self, row: Contract, closing_reason: str = "") -> bool:
        """Recompute the due date and close an active contract with nothing left out.

        Returns True when the contract was closed by this call.
        """
        self.db.flush()
        moved = quantities(self.db, row.items)
        numbers = [(item, balance(item, moved[item.id])) for item in row.items]
        held = [item for item, n in numbers if n["outstanding"] > 0]
        row.due_date = min(item.end_date for item in held) if held else None
        pending = any(n["to_withdraw"] > 0 for _item, n in numbers)
        if row.status == "ATIVO" and not held and not pending:
            row.status = "ENCERRADO"
            row.status_reason = closing_reason or row.status_reason
            self.event(row, "ENCERRADO", closing_reason or "Todos os itens foram devolvidos.")
            return True
        return False

    # ---- numbering -----------------------------------------------------------------

    def numbering(self) -> dict:
        setting = self.db.get(AppSetting, NUMBERING_KEY)
        configured = setting.value["next_number"] if setting else None
        highest = self.db.scalar(select(func.max(Contract.base_number))) or 0
        return {
            "configured": configured,
            "highest_used": highest or None,
            "next_number": max(configured or 1, highest + 1),
        }

    def set_numbering(self, payload) -> dict:
        current = self.numbering()
        if payload.next_number <= (current["highest_used"] or 0):
            raise HTTPException(
                409,
                f"Já existe contrato com número {current['highest_used']}; "
                "o próximo número precisa ser maior.",
            )
        setting = self.db.get(AppSetting, NUMBERING_KEY)
        before = current["configured"]
        if setting is None:
            setting = AppSetting(key=NUMBERING_KEY, value={})
            self.db.add(setting)
        setting.value = {"next_number": payload.next_number}
        setting.updated_at = int(time.time())
        setting.updated_by = self.actor.id
        self.identity.audit(
            "contract.numbering_changed",
            "app_settings",
            NUMBERING_KEY,
            {"before": before, "after": payload.next_number},
        )
        self.db.flush()
        return self.numbering()

    # ---- creation and editing ------------------------------------------------------

    def item_fields(self, position, line, start: date, previous) -> dict:
        fields = self.pricing.line_fields(position, line, start, previous)
        product = self.db.get(Product, line.product_id)
        return {
            **fields,
            "description": product.description,
            "individual_tracking": product.individual_tracking,
            "start_date": start.isoformat(),
        }

    def apply_items(self, row: Contract, items: list[ContractItem]):
        total = sum(item.total_cents for item in items)
        if total > calc.MAX_CENTS:
            raise HTTPException(422, "Total do contrato excede o limite permitido.")
        row.items = items
        row.total_cents = total
        row.end_date = max(item.end_date for item in items)

    def save(self, payload, record_id=None) -> dict:
        row = self.get(record_id) if record_id else None
        before = self.view(row) if row else None
        keep = {}
        if row:
            self.version(row, payload.version)
            if row.status != "RASCUNHO":
                raise HTTPException(409, "Somente contrato em rascunho pode ser editado.")
            if not payload.refresh_prices and row.start_date == payload.start_date.isoformat():
                keep = {(item.product_id, item.period): item for item in row.items}
        customer = self.pricing.customer(payload.customer_id)
        items = [
            ContractItem(
                **self.item_fields(
                    position, line, payload.start_date, keep.get((line.product_id, line.period))
                )
            )
            for position, line in enumerate(payload.items, 1)
        ]
        created = row is None
        if created:
            row = Contract(
                base_number=self.numbering()["next_number"],
                renewal_number=0,
                origin="DIRETO",
                status="RASCUNHO",
                created_by=self.actor.id,
            )
            self.db.add(row)
        else:
            self.touch(row)
        row.customer_id = customer.id
        row.customer_snapshot = self.pricing.customer_snapshot(customer)
        row.start_date = payload.start_date.isoformat()
        row.notes = payload.notes
        self.apply_items(row, items)
        self.db.flush()
        if created:
            self.event(row, "CRIADO", f"Contrato {row.number} criado.")
        self.audit("contract.created" if created else "contract.updated", row, before)
        return self.view(row)

    def from_quote(self, quote_id, payload) -> dict:
        """Approved quote becomes a draft contract exactly once, with its own snapshots."""
        today = business_today()
        quote = self.db.get(Quote, quote_id)
        if quote is None:
            raise HTTPException(404, "Orçamento não encontrado.")
        if quote.version != payload.version:
            raise HTTPException(
                409, "Orçamento alterado por outra operação. Atualize e tente novamente."
            )
        existing = self.db.scalar(select(Contract).where(Contract.quote_id == quote.id))
        if existing is not None:
            raise HTTPException(
                409, f"Este orçamento já foi convertido no contrato {existing.number}."
            )
        if effective_status(quote, today) != "APROVADO":
            raise HTTPException(409, "Somente orçamento aprovado pode ser convertido em contrato.")
        customer = self.pricing.customer(quote.customer_id)
        items = []
        for item in quote.items:
            product = self.db.get(Product, item.product_id)
            items.append(
                ContractItem(
                    position=item.position,
                    product_id=item.product_id,
                    product_code=item.product_code,
                    product_name=item.product_name,
                    description=product.description,
                    unit=item.unit,
                    individual_tracking=product.individual_tracking,
                    quantity_milli=item.quantity_milli,
                    period=item.period,
                    period_count=item.period_count,
                    price_id=item.price_id,
                    table_price_cents=item.table_price_cents,
                    unit_price_cents=item.unit_price_cents,
                    total_cents=item.total_cents,
                    start_date=quote.start_date,
                    end_date=item.end_date,
                )
            )
        row = Contract(
            base_number=self.numbering()["next_number"],
            renewal_number=0,
            origin="ORCAMENTO",
            status="RASCUNHO",
            quote_id=quote.id,
            customer_id=customer.id,
            customer_snapshot=self.pricing.customer_snapshot(customer),
            start_date=quote.start_date,
            notes=quote.notes,
            created_by=self.actor.id,
        )
        self.db.add(row)
        self.apply_items(row, items)
        self.db.flush()
        quote_before = quote_view(quote, today)
        quote.transitions.append(
            QuoteTransition(
                from_status=quote.status,
                to_status="CONVERTIDO",
                reason=f"Convertido no contrato {row.number}",
                created_by=self.actor.id,
            )
        )
        quote.status = "CONVERTIDO"
        quote.status_reason = f"Convertido no contrato {row.number}"
        quote.version += 1
        quote.updated_at = int(time.time())
        self.db.flush()
        self.identity.audit(
            "quote.converted",
            "quotes",
            quote.id,
            {"before": quote_before, "after": quote_view(quote, today)},
        )
        self.event(row, "CRIADO", f"Contrato {row.number} criado do orçamento {quote.number}.")
        self.audit("contract.created", row)
        return self.view(row)

    # ---- state transitions ---------------------------------------------------------

    def confirm(self, record_id, payload) -> dict:
        row = self.get(record_id)
        self.version(row, payload.version)
        if row.status != "RASCUNHO":
            raise HTTPException(409, "Somente contrato em rascunho pode ser confirmado.")
        self.pricing.customer(row.customer_id)
        before = self.view(row)
        row.status = "AGUARDANDO_RETIRADA"
        self.touch(row)
        self.event(row, "CONFIRMADO", f"Contrato {row.number} confirmado; aguardando retirada.")
        self.audit("contract.confirmed", row, before)
        return self.view(row)

    def cancel(self, record_id, payload) -> dict:
        row = self.get(record_id)
        self.version(row, payload.version)
        if row.status not in {"RASCUNHO", "AGUARDANDO_RETIRADA"}:
            raise HTTPException(
                409,
                "Contrato com retirada registrada não pode ser cancelado; registre a devolução.",
            )
        reason = self.reason(payload)
        before = self.view(row)
        row.status = "CANCELADO"
        row.status_reason = reason
        self.touch(row)
        self.event(row, "CANCELADO", f"Contrato {row.number} cancelado: {reason}")
        self.audit("contract.cancelled", row, before)
        return self.view(row)

    def close(self, record_id, payload) -> dict:
        """Manual closing for an active contract whose remaining quantity was never picked up."""
        row = self.get(record_id)
        self.version(row, payload.version)
        if row.status != "ATIVO":
            raise HTTPException(409, "Somente contrato ativo pode ser encerrado.")
        moved = quantities(self.db, row.items)
        if any(balance(item, moved[item.id])["outstanding"] > 0 for item in row.items):
            raise HTTPException(
                409, "Ainda há itens com o cliente. Registre a devolução antes de encerrar."
            )
        reason = self.reason(payload)
        before = self.view(row)
        row.status = "ENCERRADO"
        row.status_reason = reason
        row.due_date = None
        self.touch(row)
        self.event(row, "ENCERRADO", f"Contrato {row.number} encerrado: {reason}")
        self.audit("contract.closed", row, before)
        return self.view(row)


def movement_view(row) -> dict:
    return {
        "id": row.id,
        "occurred_on": row.occurred_on,
        "notes": row.notes,
        "created_at": row.created_at,
        "created_by": row.created_by,
        "items": [
            {
                "contract_item_id": item.contract_item_id,
                "quantity": calc.quantity(item.quantity_milli),
                "equipment_id": item.equipment_id,
                **(
                    {
                        "condition": item.condition,
                        "destination": item.destination,
                        "notes": item.notes,
                    }
                    if isinstance(item, ReturnItem)
                    else {}
                ),
            }
            for item in row.items
        ],
    }


def document_view(row: ContractDocument) -> dict:
    return {
        "id": row.id,
        "contract_id": row.contract_id,
        "template_id": row.template_id,
        "version": row.version,
        "status": row.status,
        "reason": row.reason,
        "checksum": row.checksum,
        "size": row.size,
        "signed_at": row.signed_at,
        "signed_by": row.signed_by,
        "created_at": row.created_at,
        "created_by": row.created_by,
    }


def page(
    db,
    soon_days=3,
    q="",
    status=None,
    customer_id=None,
    product="",
    equipment="",
    period=None,
    start_from=None,
    start_to=None,
    offset=0,
    limit=20,
):
    today = business_today()
    soon = (today + timedelta(days=soon_days)).isoformat()
    stmt = select(Contract).join(Customer, Customer.id == Contract.customer_id)
    if q:
        text = q.strip()
        conditions = [
            Customer.legal_name.icontains(text, autoescape=True),
            Customer.trade_name.icontains(text, autoescape=True),
            Customer.document.icontains(re.sub(r"[.\s/-]", "", text) or text, autoescape=True),
        ]
        number = re.fullmatch(r"(\d{1,9})(?:\.(\d{1,4}))?", text)
        if number and number[2] is not None:
            conditions.append(
                and_(
                    Contract.base_number == int(number[1]),
                    Contract.renewal_number == int(number[2]),
                )
            )
        elif number:
            conditions.append(Contract.base_number == int(number[1]))
        stmt = stmt.where(or_(*conditions))
    if status == "VENCIDO":
        stmt = stmt.where(Contract.status == "ATIVO", Contract.due_date < today.isoformat())
    elif status == "VENCENDO":
        stmt = stmt.where(
            Contract.status == "ATIVO",
            Contract.due_date >= today.isoformat(),
            Contract.due_date <= soon,
        )
    elif status == "ATIVO":
        stmt = stmt.where(
            Contract.status == "ATIVO", or_(Contract.due_date.is_(None), Contract.due_date > soon)
        )
    elif status:
        stmt = stmt.where(Contract.status == status)
    if customer_id is not None:
        stmt = stmt.where(Contract.customer_id == customer_id)
    if product or period:
        lines = select(ContractItem.contract_id)
        if product:
            lines = lines.where(
                or_(
                    ContractItem.product_code.icontains(product, autoescape=True),
                    ContractItem.product_name.icontains(product, autoescape=True),
                )
            )
        if period:
            lines = lines.where(ContractItem.period == period)
        stmt = stmt.where(Contract.id.in_(lines))
    if equipment:
        # Any unit that is or was under the contract, by code, asset tag or serial number.
        stmt = stmt.where(
            Contract.id.in_(
                select(ContractItem.contract_id)
                .join(ItemUnit, ItemUnit.contract_item_id == ContractItem.id)
                .join(Equipment, Equipment.id == ItemUnit.equipment_id)
                .where(
                    or_(
                        Equipment.code.icontains(equipment, autoescape=True),
                        Equipment.asset_tag.icontains(equipment, autoescape=True),
                        Equipment.serial_number.icontains(equipment, autoescape=True),
                    )
                )
            )
        )
    if start_from:
        stmt = stmt.where(Contract.start_date >= start_from.isoformat())
    if start_to:
        stmt = stmt.where(Contract.start_date <= start_to.isoformat())
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(
        db.scalars(
            stmt.order_by(
                Contract.base_number.desc(), Contract.renewal_number.desc(), Contract.id.desc()
            )
            .offset(offset)
            .limit(limit)
        )
    )
    return {"items": [summary(row, today, soon_days) for row in rows], "total": total}
