"""Read-only dashboard and reports. Contracted value is never reported as money received."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, or_, select

from app.contracts.models import (
    Contract,
    ContractDocument,
    ContractEvent,
    ContractItem,
    ItemUnit,
    RentalReturn,
    ReturnItem,
)
from app.contracts.service import balance, display_status, document_view, quantities, summary
from app.core.clock import BUSINESS_TZ, business_today
from app.masters.models import Customer, Equipment, Product, StockMovement
from app.masters.service import MasterService
from app.quotes import calc
from app.quotes.models import Quote

# Contracts that represent agreed business: drafts and cancellations are excluded.
COMMITTED = ("AGUARDANDO_RETIRADA", "ATIVO", "ENCERRADO")
EXPORT_LIMIT = 20_000


@dataclass
class Filters:
    date_from: date | None = None
    date_to: date | None = None
    customer_id: int | None = None
    product_id: int | None = None
    q: str = ""

    def between(self, column):
        conditions = []
        if self.date_from:
            conditions.append(column >= self.date_from.isoformat())
        if self.date_to:
            conditions.append(column <= self.date_to.isoformat())
        return conditions

    def day_in_range(self, day: str) -> bool:
        return not (
            (self.date_from and day < self.date_from.isoformat())
            or (self.date_to and day > self.date_to.isoformat())
        )


def business_day(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, BUSINESS_TZ).date().isoformat()


def column(key, label, kind="text"):
    return {"key": key, "label": label, "type": kind}


class ReportService:
    def __init__(self, db, actor, soon_days: int = 3):
        self.db = db
        self.actor = actor
        self.soon_days = soon_days
        self.today = business_today()
        self.soon = (self.today + timedelta(days=soon_days)).isoformat()
        self.masters = MasterService(db, actor)

    # ---- dashboard -----------------------------------------------------------------

    def count(self, *conditions) -> int:
        return self.db.scalar(select(func.count()).select_from(Contract).where(*conditions))

    def rented_milli(self) -> int:
        """Everything currently LOCADO: physical units plus quantity-controlled balances."""
        units = self.db.scalar(
            select(func.count()).select_from(Equipment).where(Equipment.status == "LOCADO")
        )
        base = (
            select(func.coalesce(func.sum(StockMovement.quantity_milli), 0))
            .join(Product, Product.id == StockMovement.product_id)
            .where(Product.individual_tracking.is_(False))
        )
        entered = self.db.scalar(base.where(StockMovement.to_status == "LOCADO"))
        left = self.db.scalar(base.where(StockMovement.from_status == "LOCADO"))
        return units * 1000 + entered - left

    def dashboard(self) -> dict:
        today = self.today.isoformat()
        active = Contract.status == "ATIVO"
        equipment = dict(
            self.db.execute(select(Equipment.status, func.count()).group_by(Equipment.status)).all()
        )
        due = self.db.scalars(
            select(Contract)
            .where(active, Contract.due_date <= self.soon)
            .order_by(Contract.due_date)
            .limit(10)
        )
        events = self.db.execute(
            select(ContractEvent, Contract)
            .join(Contract, Contract.id == ContractEvent.contract_id)
            .order_by(ContractEvent.id.desc())
            .limit(10)
        )
        contracted = self.db.scalar(
            select(func.coalesce(func.sum(Contract.total_cents), 0)).where(active)
        )
        return {
            "cards": {
                "active_contracts": self.count(active),
                "awaiting_withdrawal": self.count(Contract.status == "AGUARDANDO_RETIRADA"),
                "due_soon": self.count(
                    active, Contract.due_date >= today, Contract.due_date <= self.soon
                ),
                "overdue": self.count(active, Contract.due_date < today),
                "rented_items": calc.quantity(self.rented_milli()),
                "equipment_available": equipment.get("DISPONIVEL", 0),
                "equipment_maintenance": equipment.get("MANUTENCAO", 0),
                # Sum of active contracts as agreed; it is not cash received.
                "contracted_value": calc.money(contracted),
                "open_quotes": self.db.scalar(
                    select(func.count())
                    .select_from(Quote)
                    .where(Quote.status == "ENVIADO", Quote.valid_until >= today)
                ),
            },
            "due_soon_days": self.soon_days,
            "due_contracts": [summary(row, self.today, self.soon_days) for row in due],
            "recent_events": [
                {
                    "id": event.id,
                    "contract_id": contract.id,
                    "contract_number": contract.number,
                    "customer": contract.customer_snapshot["legal_name"],
                    "kind": event.kind,
                    "description": event.description,
                    "created_at": event.created_at,
                }
                for event, contract in events
            ],
        }

    # ---- customer page -------------------------------------------------------------

    def customer(self, customer_id: int) -> dict:
        if self.db.get(Customer, customer_id) is None:
            raise HTTPException(404, "Cliente não encontrado.")
        contracts = list(
            self.db.scalars(
                select(Contract)
                .where(Contract.customer_id == customer_id)
                .order_by(Contract.base_number.desc(), Contract.renewal_number.desc())
            )
        )
        active = [row for row in contracts if row.status == "ATIVO"]
        items = [item for row in active for item in row.items]
        moved = quantities(self.db, items)
        rented = sum(balance(item, moved[item.id])["outstanding"] for item in items)
        documents = self.db.execute(
            select(ContractDocument, Contract)
            .join(Contract, Contract.id == ContractDocument.contract_id)
            .where(Contract.customer_id == customer_id)
            .order_by(ContractDocument.id.desc())
        )
        return {
            "active_contracts": len(active),
            "total_contracts": len(contracts),
            "rented_items": calc.quantity(rented),
            "contracted_value": calc.money(sum(row.total_cents for row in active)),
            "contracts": [summary(row, self.today, self.soon_days) for row in contracts],
            "documents": [
                {**document_view(document), "contract_number": contract.number}
                for document, contract in documents
            ],
        }

    # ---- reports -------------------------------------------------------------------

    def contract_rows(self, f: Filters, *conditions):
        stmt = select(Contract).where(*conditions, *f.between(Contract.start_date))
        if f.customer_id:
            stmt = stmt.where(Contract.customer_id == f.customer_id)
        if f.product_id:
            stmt = stmt.where(
                Contract.id.in_(
                    select(ContractItem.contract_id).where(ContractItem.product_id == f.product_id)
                )
            )
        rows = self.db.scalars(stmt.order_by(Contract.due_date, Contract.base_number))
        return [
            {
                "contract_id": row.id,
                "number": row.number,
                "customer": row.customer_snapshot["legal_name"],
                "document": row.customer_snapshot["document"],
                "start_date": row.start_date,
                "due_date": row.due_date,
                "end_date": row.end_date,
                "status": display_status(row, self.today, self.soon_days),
                "total": calc.money(row.total_cents),
            }
            for row in rows
        ]

    CONTRACT_COLUMNS = [
        column("number", "Contrato"),
        column("customer", "Cliente"),
        column("document", "CPF/CNPJ"),
        column("start_date", "Início", "date"),
        column("due_date", "Devolução prevista", "date"),
        column("status", "Situação", "status"),
        column("total", "Valor contratado", "money"),
    ]

    def active_rentals(self, f):
        return self.contract_rows(f, Contract.status == "ATIVO")

    def due_soon(self, f):
        return self.contract_rows(
            f,
            Contract.status == "ATIVO",
            Contract.due_date >= self.today.isoformat(),
            Contract.due_date <= self.soon,
        )

    def overdue(self, f):
        return self.contract_rows(
            f, Contract.status == "ATIVO", Contract.due_date < self.today.isoformat()
        )

    def stock_rows(self, f: Filters, status: str):
        stmt = select(Product).where(Product.is_active)
        if f.product_id:
            stmt = stmt.where(Product.id == f.product_id)
        if f.q:
            stmt = stmt.where(
                or_(
                    Product.code.icontains(f.q, autoescape=True),
                    Product.name.icontains(f.q, autoescape=True),
                )
            )
        rows = []
        for product in self.db.scalars(stmt.order_by(Product.code)):
            balances = self.masters.balances(product)
            if balances[status] <= 0:
                continue
            rows.append(
                {
                    "code": product.code,
                    "name": product.name,
                    "unit": product.unit,
                    "available": calc.quantity(balances["DISPONIVEL"]),
                    "rented": calc.quantity(balances["LOCADO"]),
                    "maintenance": calc.quantity(balances["MANUTENCAO"]),
                }
            )
        return rows

    STOCK_COLUMNS = [
        column("code", "Código"),
        column("name", "Produto"),
        column("unit", "Unidade"),
        column("available", "Disponível", "quantity"),
        column("rented", "Locado", "quantity"),
        column("maintenance", "Manutenção", "quantity"),
    ]

    def rented_products(self, f):
        return self.stock_rows(f, "LOCADO")

    def available_products(self, f):
        return self.stock_rows(f, "DISPONIVEL")

    def equipment_by_customer(self, f):
        stmt = select(Contract).where(Contract.status == "ATIVO")
        if f.customer_id:
            stmt = stmt.where(Contract.customer_id == f.customer_id)
        rows = []
        for contract in self.db.scalars(stmt.order_by(Contract.base_number)):
            moved = quantities(self.db, contract.items)
            for item in contract.items:
                if f.product_id and item.product_id != f.product_id:
                    continue
                outstanding = balance(item, moved[item.id])["outstanding"]
                if outstanding <= 0:
                    continue
                shared = {
                    "contract_id": contract.id,
                    "customer": contract.customer_snapshot["legal_name"],
                    "number": contract.number,
                    "product": f"{item.product_code} — {item.product_name}",
                    "due_date": item.end_date,
                }
                if not item.individual_tracking:
                    rows.append({**shared, "equipment": "", "quantity": calc.quantity(outstanding)})
                    continue
                codes = self.db.scalars(
                    select(Equipment.code)
                    .join(ItemUnit, ItemUnit.equipment_id == Equipment.id)
                    .where(ItemUnit.contract_item_id == item.id, ItemUnit.state == "EM_POSSE")
                    .order_by(Equipment.code)
                )
                rows += [{**shared, "equipment": code, "quantity": "1.000"} for code in codes]
        return rows

    def equipment_history(self, f):
        stmt = (
            select(StockMovement, Equipment)
            .join(Equipment, Equipment.id == StockMovement.equipment_id)
            .order_by(StockMovement.id.desc())
        )
        if f.q:
            stmt = stmt.where(
                or_(
                    Equipment.code.icontains(f.q, autoescape=True),
                    Equipment.asset_tag.icontains(f.q, autoescape=True),
                    Equipment.serial_number.icontains(f.q, autoescape=True),
                )
            )
        if f.product_id:
            stmt = stmt.where(Equipment.product_id == f.product_id)
        rows = []
        for movement, equipment in self.db.execute(stmt.limit(EXPORT_LIMIT)):
            day = business_day(movement.created_at)
            if f.day_in_range(day):
                rows.append(
                    {
                        "date": day,
                        "equipment": equipment.code,
                        "product": f"{equipment.product.code} — {equipment.product.name}",
                        "from_status": movement.from_status or "",
                        "to_status": movement.to_status,
                        "reason": movement.reason,
                    }
                )
        return rows

    def renewals(self, f):
        stmt = select(Contract).where(
            Contract.origin == "RENOVACAO", *f.between(Contract.start_date)
        )
        if f.customer_id:
            stmt = stmt.where(Contract.customer_id == f.customer_id)
        rows = []
        for row in self.db.scalars(stmt.order_by(Contract.base_number, Contract.renewal_number)):
            previous = self.db.get(Contract, row.previous_id)
            rows.append(
                {
                    "contract_id": row.id,
                    "number": row.number,
                    "previous": previous.number if previous else "",
                    "customer": row.customer_snapshot["legal_name"],
                    "start_date": row.start_date,
                    "end_date": row.end_date,
                    "price_option": row.price_option,
                    "total": calc.money(row.total_cents),
                }
            )
        return rows

    def returns(self, f):
        stmt = (
            select(ReturnItem, RentalReturn, Contract, ContractItem)
            .join(RentalReturn, RentalReturn.id == ReturnItem.return_id)
            .join(Contract, Contract.id == RentalReturn.contract_id)
            .join(ContractItem, ContractItem.id == ReturnItem.contract_item_id)
            .where(*f.between(RentalReturn.occurred_on))
            .order_by(RentalReturn.occurred_on.desc(), ReturnItem.id.desc())
        )
        if f.customer_id:
            stmt = stmt.where(Contract.customer_id == f.customer_id)
        if f.product_id:
            stmt = stmt.where(ContractItem.product_id == f.product_id)
        rows = []
        for line, returned, contract, item in self.db.execute(stmt.limit(EXPORT_LIMIT)):
            equipment = self.db.get(Equipment, line.equipment_id) if line.equipment_id else None
            rows.append(
                {
                    "contract_id": contract.id,
                    "date": returned.occurred_on,
                    "number": contract.number,
                    "customer": contract.customer_snapshot["legal_name"],
                    "product": f"{item.product_code} — {item.product_name}",
                    "equipment": equipment.code if equipment else "",
                    "quantity": calc.quantity(line.quantity_milli),
                    "condition": line.condition,
                    "destination": line.destination,
                    "notes": line.notes,
                }
            )
        return rows

    def committed(self, f: Filters):
        stmt = select(Contract).where(
            Contract.status.in_(COMMITTED), *f.between(Contract.start_date)
        )
        if f.customer_id:
            stmt = stmt.where(Contract.customer_id == f.customer_id)
        return list(self.db.scalars(stmt))

    def contracted_revenue(self, f):
        months: dict[str, list[int]] = {}
        for row in self.committed(f):
            bucket = months.setdefault(row.start_date[:7], [0, 0])
            bucket[0] += 1
            bucket[1] += row.total_cents
        return [
            {"month": month, "contracts": count, "total": calc.money(total)}
            for month, (count, total) in sorted(months.items())
        ]

    def top_products(self, f):
        products: dict[int, dict] = {}
        for contract in self.committed(f):
            for item in contract.items:
                if f.product_id and item.product_id != f.product_id:
                    continue
                row = products.setdefault(
                    item.product_id,
                    {"code": item.product_code, "name": item.product_name, "n": 0, "q": 0, "t": 0},
                )
                row["n"] += 1
                row["q"] += item.quantity_milli
                row["t"] += item.total_cents
        ranked = sorted(products.values(), key=lambda row: (-row["n"], -row["t"], row["code"]))
        return [
            {
                "code": row["code"],
                "name": row["name"],
                "rentals": row["n"],
                "quantity": calc.quantity(row["q"]),
                "total": calc.money(row["t"]),
            }
            for row in ranked
        ]

    def top_customers(self, f):
        customers: dict[int, dict] = {}
        for contract in self.committed(f):
            row = customers.setdefault(
                contract.customer_id,
                {
                    "customer": contract.customer_snapshot["legal_name"],
                    "document": contract.customer_snapshot["document"],
                    "n": 0,
                    "t": 0,
                },
            )
            row["n"] += 1
            row["t"] += contract.total_cents
        ranked = sorted(customers.values(), key=lambda row: (-row["t"], row["customer"]))
        return [
            {
                "customer": row["customer"],
                "document": row["document"],
                "contracts": row["n"],
                "total": calc.money(row["t"]),
            }
            for row in ranked
        ]

    def run(self, key: str, f: Filters) -> dict:
        definition = REPORTS.get(key)
        if definition is None:
            raise HTTPException(404, "Relatório não encontrado.")
        rows = getattr(self, key)(f)
        return {
            "key": key,
            "title": definition["title"],
            "note": definition.get("note", ""),
            "columns": definition["columns"],
            "rows": rows,
        }


REVENUE_NOTE = "Valores contratados conforme os contratos; não representam pagamentos recebidos."
REPORTS = {
    "active_rentals": {"title": "Locações ativas", "columns": ReportService.CONTRACT_COLUMNS},
    "due_soon": {"title": "Contratos vencendo", "columns": ReportService.CONTRACT_COLUMNS},
    "overdue": {"title": "Contratos vencidos", "columns": ReportService.CONTRACT_COLUMNS},
    "rented_products": {"title": "Produtos locados", "columns": ReportService.STOCK_COLUMNS},
    "available_products": {
        "title": "Produtos disponíveis",
        "columns": ReportService.STOCK_COLUMNS,
    },
    "equipment_by_customer": {
        "title": "Equipamentos por cliente",
        "columns": [
            column("customer", "Cliente"),
            column("number", "Contrato"),
            column("product", "Produto"),
            column("equipment", "Equipamento"),
            column("quantity", "Quantidade", "quantity"),
            column("due_date", "Devolução prevista", "date"),
        ],
    },
    "equipment_history": {
        "title": "Histórico de equipamento",
        "columns": [
            column("date", "Data", "date"),
            column("equipment", "Equipamento"),
            column("product", "Produto"),
            column("from_status", "De", "status"),
            column("to_status", "Para", "status"),
            column("reason", "Motivo"),
        ],
    },
    "renewals": {
        "title": "Renovações",
        "note": REVENUE_NOTE,
        "columns": [
            column("number", "Renovação"),
            column("previous", "Contrato anterior"),
            column("customer", "Cliente"),
            column("start_date", "Início", "date"),
            column("end_date", "Devolução prevista", "date"),
            column("price_option", "Preços", "status"),
            column("total", "Valor contratado", "money"),
        ],
    },
    "returns": {
        "title": "Devoluções",
        "columns": [
            column("date", "Data", "date"),
            column("number", "Contrato"),
            column("customer", "Cliente"),
            column("product", "Produto"),
            column("equipment", "Equipamento"),
            column("quantity", "Quantidade", "quantity"),
            column("condition", "Condição", "status"),
            column("destination", "Destino", "status"),
            column("notes", "Observação"),
        ],
    },
    "contracted_revenue": {
        "title": "Receita contratada por período",
        "note": REVENUE_NOTE,
        "columns": [
            column("month", "Mês de início"),
            column("contracts", "Contratos", "int"),
            column("total", "Valor contratado", "money"),
        ],
    },
    "top_products": {
        "title": "Produtos mais locados",
        "note": REVENUE_NOTE,
        "columns": [
            column("code", "Código"),
            column("name", "Produto"),
            column("rentals", "Locações", "int"),
            column("quantity", "Quantidade", "quantity"),
            column("total", "Valor contratado", "money"),
        ],
    },
    "top_customers": {
        "title": "Clientes com maior volume",
        "note": REVENUE_NOTE,
        "columns": [
            column("customer", "Cliente"),
            column("document", "CPF/CNPJ"),
            column("contracts", "Contratos", "int"),
            column("total", "Valor contratado", "money"),
        ],
    },
}
