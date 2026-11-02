"""Quote rules. Caller owns a serialized transaction and commit."""

import re
import time
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select

from app.auth.catalog import permission_codes
from app.auth.service import IdentityService
from app.core.clock import BUSINESS_TZ, business_today
from app.masters.models import Customer, Price, Product
from app.masters.service import MasterService
from app.quotes import calc
from app.quotes.models import Quote, QuoteItem, QuoteTransition

CUSTOMER_FIELDS = (
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
PERIOD_LABELS = {
    "DIARIA": "diária",
    "SEMANAL": "semanal",
    "QUINZENAL": "quinzenal",
    "MENSAL": "mensal",
}
STATUS_LABELS = {
    "RASCUNHO": "em rascunho",
    "ENVIADO": "enviado",
    "APROVADO": "aprovado",
    "REJEITADO": "rejeitado",
    "EXPIRADO": "expirado",
    "CANCELADO": "cancelado",
    "CONVERTIDO": "convertido",
}
# action -> (stored statuses that allow it, resulting status, audit action)
TRANSITIONS = {
    "send": ({"RASCUNHO"}, "ENVIADO", "quote.sent"),
    "approve": ({"RASCUNHO", "ENVIADO"}, "APROVADO", "quote.approved"),
    "reject": ({"ENVIADO"}, "REJEITADO", "quote.rejected"),
    "cancel": ({"RASCUNHO", "ENVIADO", "APROVADO"}, "CANCELADO", "quote.cancelled"),
    "reopen": ({"ENVIADO"}, "RASCUNHO", "quote.reopened"),
}


def effective_status(row: Quote, today: date) -> str:
    if row.status == "ENVIADO" and row.valid_until < today.isoformat():
        return "EXPIRADO"
    return row.status


def item_view(item: QuoteItem) -> dict:
    return {
        "id": item.id,
        "position": item.position,
        "product_id": item.product_id,
        "product_code": item.product_code,
        "product_name": item.product_name,
        "unit": item.unit,
        "quantity": calc.quantity(item.quantity_milli),
        "period": item.period,
        "period_count": item.period_count,
        "table_price": calc.money(item.table_price_cents),
        "unit_price": calc.money(item.unit_price_cents),
        "negotiated": item.unit_price_cents != item.table_price_cents,
        "total": calc.money(item.total_cents),
        "end_date": item.end_date,
    }


def summary(row: Quote, today: date) -> dict:
    return {
        "id": row.id,
        "number": row.number,
        "status": effective_status(row, today),
        "status_reason": row.status_reason,
        "customer_id": row.customer_id,
        "customer": row.customer_snapshot,
        "start_date": row.start_date,
        "valid_until": row.valid_until,
        "notes": row.notes,
        "total": calc.money(row.total_cents),
        "item_count": len(row.items),
        "duplicated_from_id": row.duplicated_from_id,
        "version": row.version,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "created_by": row.created_by,
    }


def view(row: Quote, today: date) -> dict:
    table_total = sum(
        calc.item_total_cents(i.quantity_milli, i.table_price_cents, i.period_count)
        for i in row.items
    )
    return {
        **summary(row, today),
        "table_total": calc.money(table_total),
        # Positive when the negotiated total is below the price table.
        "negotiated_difference": calc.signed_money(table_total - row.total_cents),
        "items": [item_view(item) for item in row.items],
        "transitions": [
            {
                "from_status": t.from_status,
                "to_status": t.to_status,
                "reason": t.reason,
                "created_at": t.created_at,
                "created_by": t.created_by,
            }
            for t in row.transitions
        ],
    }


class QuoteService:
    def __init__(self, db, actor):
        self.db = db
        self.actor = actor
        self.identity = IdentityService(db, actor)
        self.can_negotiate = "quotes.negotiate" in permission_codes(actor)

    def get(self, record_id) -> Quote:
        row = self.db.get(Quote, record_id)
        if row is None:
            raise HTTPException(404, "Orçamento não encontrado.")
        return row

    def detail(self, record_id) -> dict:
        return view(self.get(record_id), business_today())

    def version(self, row, version):
        if row.version != version:
            raise HTTPException(
                409, "Orçamento alterado por outra operação. Atualize e tente novamente."
            )

    def audit(self, action, row, before, today):
        self.identity.audit(action, "quotes", row.id, {"before": before, "after": view(row, today)})
        # Audit failure must fail the entire operation, before any response is sent.
        self.db.flush()

    def customer(self, customer_id) -> Customer:
        customer = self.db.get(Customer, customer_id)
        if customer is None:
            raise HTTPException(404, "Cliente não encontrado.")
        if not customer.is_active:
            raise HTTPException(409, "Cliente desativado não pode receber orçamento.")
        return customer

    def product(self, product_id) -> Product:
        product = self.db.get(Product, product_id)
        if product is None:
            raise HTTPException(404, "Produto não encontrado.")
        if not product.is_active:
            raise HTTPException(409, f"Produto {product.code} está desativado.")
        return product

    def table_price(self, product: Product, period: str, at: date):
        """Latest revision of the price in force; a retired revision means no price."""
        row = self.db.scalar(
            select(Price)
            .where(
                Price.product_id == product.id,
                Price.period == period,
                Price.effective_date <= at.isoformat(),
            )
            .order_by(Price.effective_date.desc(), Price.id.desc())
            .limit(1)
        )
        if row is None or row.amount_cents is None:
            return None
        return row

    def pricing(self, product_id: int, period: str, at: date) -> dict:
        """Read-only helper for the editor: table price and stock shown, nothing reserved."""
        product = self.product(product_id)
        price = self.table_price(product, period, at)
        available = MasterService(self.db, self.actor).balances(product)["DISPONIVEL"]
        return {
            "product_id": product.id,
            "product_code": product.code,
            "product_name": product.name,
            "unit": product.unit,
            "individual_tracking": product.individual_tracking,
            "period": period,
            "at": at.isoformat(),
            "price_id": price.id if price else None,
            "table_price": calc.money(price.amount_cents) if price else None,
            "available": calc.quantity(available),
            "period_days": calc.PERIOD_DAYS[period],
        }

    def build_item(self, position, line, start: date, previous: QuoteItem | None) -> QuoteItem:
        return QuoteItem(**self.line_fields(position, line, start, previous))

    def line_fields(self, position, line, start: date, previous) -> dict:
        """Priced line shared by quotes and contracts; `previous` is a saved item snapshot."""
        product = self.product(line.product_id)
        quantity_milli = int(line.quantity * 1000)
        if product.individual_tracking and quantity_milli % 1000:
            raise HTTPException(
                422, f"Produto {product.code} é controlado por unidade: use quantidade inteira."
            )
        if previous:
            # Saved snapshot stays until the user explicitly refreshes prices.
            price_id, table = previous.price_id, previous.table_price_cents
        else:
            price = self.table_price(product, line.period, start)
            if price is None:
                raise HTTPException(
                    409,
                    f"Não há preço {PERIOD_LABELS[line.period]} vigente para {product.code} "
                    f"em {start.strftime('%d/%m/%Y')}.",
                )
            price_id, table = price.id, price.amount_cents
        unit = table if line.unit_price is None else int(line.unit_price * 100)
        unchanged = previous is not None and previous.unit_price_cents == unit
        if unit != table and not unchanged and not self.can_negotiate:
            raise HTTPException(403, "Você não tem permissão para alterar o preço de tabela.")
        total = calc.item_total_cents(quantity_milli, unit, line.period_count)
        if total > calc.MAX_CENTS:
            raise HTTPException(422, "Valor do item excede o limite permitido.")
        return dict(
            position=position,
            product_id=product.id,
            product_code=product.code,
            product_name=product.name,
            unit=product.unit,
            quantity_milli=quantity_milli,
            period=line.period,
            period_count=line.period_count,
            price_id=price_id,
            table_price_cents=table,
            unit_price_cents=unit,
            total_cents=total,
            end_date=calc.end_date(start, line.period, line.period_count).isoformat(),
        )

    def customer_snapshot(self, customer: Customer) -> dict:
        data = {key: getattr(customer, key) for key in CUSTOMER_FIELDS}
        address = customer.addresses[0] if customer.addresses else None
        data["address"] = (
            {key: getattr(address, key) for key in ("street", "city", "state", "postal_code")}
            if address
            else None
        )
        return data

    def next_number(self, year: int) -> int:
        # Serialized by BEGIN IMMEDIATE; the unique constraint is the final guard.
        return (self.db.scalar(select(func.max(Quote.sequence)).where(Quote.year == year)) or 0) + 1

    def apply_total(self, row: Quote, items: list[QuoteItem]):
        total = sum(item.total_cents for item in items)
        if total > calc.MAX_CENTS:
            raise HTTPException(422, "Total do orçamento excede o limite permitido.")
        row.items = items
        row.total_cents = total

    def save(self, payload, record_id=None) -> dict:
        today = business_today()
        row = self.get(record_id) if record_id else None
        before = view(row, today) if row else None
        keep = {}
        if row:
            self.version(row, payload.version)
            if row.status != "RASCUNHO":
                raise HTTPException(
                    409, "Somente rascunhos podem ser editados. Reabra ou duplique o orçamento."
                )
            if not payload.refresh_prices and row.start_date == payload.start_date.isoformat():
                keep = {(item.product_id, item.period): item for item in row.items}
        customer = self.customer(payload.customer_id)
        if payload.valid_until < today:
            raise HTTPException(422, "A validade não pode ser anterior a hoje.")
        items = [
            self.build_item(
                position, line, payload.start_date, keep.get((line.product_id, line.period))
            )
            for position, line in enumerate(payload.items, 1)
        ]
        if row is None:
            row = Quote(
                year=today.year,
                sequence=self.next_number(today.year),
                status="RASCUNHO",
                created_by=self.actor.id,
            )
            self.db.add(row)
            row.transitions = [QuoteTransition(to_status="RASCUNHO", created_by=self.actor.id)]
        else:
            row.version += 1
            row.updated_at = int(time.time())
        row.customer_id = customer.id
        row.customer_snapshot = self.customer_snapshot(customer)
        row.start_date = payload.start_date.isoformat()
        row.valid_until = payload.valid_until.isoformat()
        row.notes = payload.notes
        self.apply_total(row, items)
        self.db.flush()
        self.audit("quote.updated" if record_id else "quote.created", row, before, today)
        return view(row, today)

    def transition(self, record_id, action, payload) -> dict:
        today = business_today()
        row = self.get(record_id)
        self.version(row, payload.version)
        allowed, target, audit_action = TRANSITIONS[action]
        current = effective_status(row, today)
        if row.status not in allowed or (action == "reject" and current == "EXPIRADO"):
            raise HTTPException(409, f"Ação indisponível para orçamento {STATUS_LABELS[current]}.")
        if action in {"send", "approve"} and row.valid_until < today.isoformat():
            raise HTTPException(
                409, "Validade vencida. Reabra o orçamento e ajuste a validade antes de continuar."
            )
        reason = payload.reason.strip()
        if action in {"reject", "cancel"} and len(reason) < 5:
            raise HTTPException(422, "Informe o motivo com pelo menos 5 caracteres.")
        before = view(row, today)
        row.transitions.append(
            QuoteTransition(
                from_status=row.status, to_status=target, reason=reason, created_by=self.actor.id
            )
        )
        row.status = target
        row.status_reason = reason
        row.version += 1
        row.updated_at = int(time.time())
        self.db.flush()
        self.audit(audit_action, row, before, today)
        return view(row, today)

    def duplicate(self, record_id, payload) -> dict:
        """New draft priced by the current table; lines that cannot be priced are reported."""
        today = business_today()
        source = self.get(record_id)
        customer = self.customer(source.customer_id)
        start = payload.start_date or today
        created = datetime.fromtimestamp(source.created_at, BUSINESS_TZ).date()
        span = max((date.fromisoformat(source.valid_until) - created).days, 1)
        valid_until = payload.valid_until or today + timedelta(days=span)
        if valid_until < today:
            raise HTTPException(422, "A validade não pode ser anterior a hoje.")
        items, warnings = [], []
        for item in source.items:
            product = self.db.get(Product, item.product_id)
            price = (
                self.table_price(product, item.period, start)
                if product and product.is_active
                else None
            )
            if price is None:
                warnings.append(
                    f"{item.product_code}: sem produto ativo ou preço {PERIOD_LABELS[item.period]} "
                    "vigente; item não copiado."
                )
                continue
            negotiated = item.unit_price_cents != item.table_price_cents
            if negotiated and not self.can_negotiate:
                warnings.append(
                    f"{item.product_code}: preço negociado não copiado; aplicado o preço de tabela."
                )
            unit = (
                item.unit_price_cents if negotiated and self.can_negotiate else price.amount_cents
            )
            items.append(
                QuoteItem(
                    position=len(items) + 1,
                    product_id=product.id,
                    product_code=product.code,
                    product_name=product.name,
                    unit=product.unit,
                    quantity_milli=item.quantity_milli,
                    period=item.period,
                    period_count=item.period_count,
                    price_id=price.id,
                    table_price_cents=price.amount_cents,
                    unit_price_cents=unit,
                    total_cents=calc.item_total_cents(item.quantity_milli, unit, item.period_count),
                    end_date=calc.end_date(start, item.period, item.period_count).isoformat(),
                )
            )
        if not items:
            raise HTTPException(
                409, "Nenhum item pôde ser copiado: confira produtos ativos e preços vigentes."
            )
        row = Quote(
            year=today.year,
            sequence=self.next_number(today.year),
            status="RASCUNHO",
            customer_id=customer.id,
            customer_snapshot=self.customer_snapshot(customer),
            start_date=start.isoformat(),
            valid_until=valid_until.isoformat(),
            notes=source.notes,
            duplicated_from_id=source.id,
            created_by=self.actor.id,
        )
        self.db.add(row)
        row.transitions = [
            QuoteTransition(
                to_status="RASCUNHO",
                reason=f"Duplicado de {source.number}",
                created_by=self.actor.id,
            )
        ]
        self.apply_total(row, items)
        self.db.flush()
        self.audit("quote.duplicated", row, None, today)
        return {**view(row, today), "warnings": warnings}


def page(db, q="", status=None, customer_id=None, offset=0, limit=20):
    today = business_today()
    stmt = select(Quote).join(Customer, Customer.id == Quote.customer_id)
    if q:
        conditions = [
            Customer.legal_name.icontains(q, autoescape=True),
            Customer.trade_name.icontains(q, autoescape=True),
            Customer.document.icontains(re.sub(r"[.\s/-]", "", q) or q, autoescape=True),
        ]
        number = re.fullmatch(r"(?:ORC-?)?(\d{4})-(\d{1,6})", q.strip().upper())
        if number:
            conditions.append(and_(Quote.year == int(number[1]), Quote.sequence == int(number[2])))
        elif re.fullmatch(r"[0-9]{1,6}", q.strip()):
            conditions.append(Quote.sequence == int(q.strip()))
        stmt = stmt.where(or_(*conditions))
    if status == "EXPIRADO":
        stmt = stmt.where(Quote.status == "ENVIADO", Quote.valid_until < today.isoformat())
    elif status == "ENVIADO":
        stmt = stmt.where(Quote.status == "ENVIADO", Quote.valid_until >= today.isoformat())
    elif status:
        stmt = stmt.where(Quote.status == status)
    if customer_id is not None:
        stmt = stmt.where(Quote.customer_id == customer_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(db.scalars(stmt.order_by(Quote.id.desc()).offset(offset).limit(limit)))
    return {"items": [summary(row, today) for row in rows], "total": total}
