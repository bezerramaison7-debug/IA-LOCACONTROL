"""Master data rules. Caller owns a serialized transaction and commit."""

import time
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select

from app.auth.service import IdentityService
from app.masters.models import (
    STATES,
    Customer,
    CustomerAddress,
    Equipment,
    Price,
    Product,
    StockMovement,
)


def view(row):
    data = {column.key: getattr(row, column.key) for column in row.__table__.columns}
    if isinstance(row, (Equipment, Price, StockMovement)):
        data["product_name"] = row.product.name
        data["product_code"] = row.product.code
    if isinstance(row, Customer):
        data["addresses"] = [
            {key: getattr(a, key) for key in ("label", "street", "city", "state", "postal_code")}
            for a in row.addresses
        ]
    if isinstance(row, Price):
        cents = data.pop("amount_cents")
        data["amount"] = format(Decimal(cents) / 100, ".2f") if cents is not None else None
        data["is_active"] = cents is not None
    if isinstance(row, StockMovement):
        data["quantity"] = format(Decimal(data.pop("quantity_milli")) / 1000, ".3f")
    return data


class MasterService:
    def __init__(self, db, actor):
        self.db = db
        self.actor = actor
        self.identity = IdentityService(db, actor)

    def get(self, model, record_id):
        row = self.db.get(model, record_id)
        if row is None:
            raise HTTPException(404, "Registro não encontrado.")
        return row

    def audit(self, action, row, before=None):
        self.identity.audit(
            action,
            row.__tablename__,
            row.id,
            {"before": before, "after": view(row)},
        )
        # Audit failure must fail the entire operation, before any response is sent.
        self.db.flush()

    def version(self, row, version):
        if row.version != version:
            raise HTTPException(
                409, "Registro alterado por outra operação. Atualize e tente novamente."
            )

    def unique(self, model, key, value, record_id=None):
        if value is None:
            return
        stmt = select(model.id).where(getattr(model, key) == value)
        if record_id:
            stmt = stmt.where(model.id != record_id)
        if self.db.scalar(stmt):
            labels = {
                "document": "CPF/CNPJ",
                "code": "Código",
                "asset_tag": "Patrimônio",
                "serial_number": "Número serial",
            }
            raise HTTPException(
                409, f"{labels.get(key, key)} já cadastrado, inclusive em registros inativos."
            )

    def save(self, model, payload, record_id=None):
        data = payload.model_dump()
        row = self.get(model, record_id) if record_id else None
        before = view(row) if row else None
        if row:
            self.version(row, data.pop("version"))
        if model is Customer:
            self.unique(model, "document", data["document"], record_id)
            addresses = data.pop("addresses")
            # Unchanged addresses keep their IDs for future references.
            if row and before["addresses"] == addresses:
                addresses = None
        else:
            self.unique(model, "code", data["code"], record_id)
        if model is Equipment:
            product = self.get(Product, data["product_id"])
            if not product.is_active or not product.individual_tracking:
                raise HTTPException(409, "Equipamento exige produto ativo com controle individual.")
            if row and row.product_id != product.id:
                raise HTTPException(409, "Não é permitido trocar o produto de uma unidade física.")
            for key in ("asset_tag", "serial_number"):
                self.unique(model, key, data[key], record_id)
        if model is Product and row:
            has_history = self.db.scalar(
                select(StockMovement.id).where(StockMovement.product_id == row.id).limit(1)
            )
            if row.individual_tracking != data["individual_tracking"] and has_history:
                raise HTTPException(409, "Controle individual não pode mudar após movimentação.")
            balances = self.balances(row)
            if not data["is_active"] and (balances["RESERVADO"] or balances["LOCADO"]):
                raise HTTPException(409, "Produto reservado ou locado não pode ser desativado.")
        if row:
            for key, value in data.items():
                setattr(row, key, value)
            row.version += 1
            row.updated_at = int(time.time())
        else:
            row = model(**data, created_by=self.actor.id)
            self.db.add(row)
        if model is Customer and addresses is not None:
            row.addresses = [CustomerAddress(**a) for a in addresses]
        self.db.flush()
        if model is Equipment and record_id is None:
            movement = StockMovement(
                product_id=row.product_id,
                equipment_id=row.id,
                from_status=None,
                to_status="DISPONIVEL",
                quantity_milli=1000,
                reason="Cadastro de unidade física",
                created_by=self.actor.id,
            )
            self.db.add(movement)
            self.db.flush()
            self.audit("stock.received", movement)
        self.audit("master.updated" if record_id else "master.created", row, before)
        return view(row)

    def deactivate(self, model, record_id, version):
        row = self.get(model, record_id)
        self.version(row, version)
        if model is Product:
            balance = self.balances(row)
            if balance["RESERVADO"] or balance["LOCADO"]:
                raise HTTPException(409, "Produto reservado ou locado não pode ser desativado.")
        before = view(row)
        row.is_active = False
        row.version += 1
        row.updated_at = int(time.time())
        self.audit("master.deactivated", row, before)
        return view(row)

    def balances(self, product):
        result = dict.fromkeys(STATES, 0)
        if product.individual_tracking:
            for status, count in self.db.execute(
                select(Equipment.status, func.count())
                .where(Equipment.product_id == product.id)
                .group_by(Equipment.status)
            ):
                result[status] = count * 1000
        else:
            for status, total in self.db.execute(
                select(StockMovement.to_status, func.sum(StockMovement.quantity_milli))
                .where(StockMovement.product_id == product.id)
                .group_by(StockMovement.to_status)
            ):
                result[status] += total
            for status, total in self.db.execute(
                select(StockMovement.from_status, func.sum(StockMovement.quantity_milli))
                .where(
                    StockMovement.product_id == product.id, StockMovement.from_status.is_not(None)
                )
                .group_by(StockMovement.from_status)
            ):
                result[status] -= total
        return result

    def stock_view(self, product):
        return {
            **view(product),
            "balances": {
                status: format(Decimal(value) / 1000, ".3f")
                for status, value in self.balances(product).items()
            },
        }

    def move(self, payload):
        values = payload.model_dump()
        key = str(values.pop("request_key"))
        quantity = int(values.pop("quantity") * 1000)
        existing = self.db.scalar(select(StockMovement).where(StockMovement.request_key == key))
        if existing:
            expected = {**values, "quantity_milli": quantity}
            if existing.created_by != self.actor.id or any(
                getattr(existing, k) != v for k, v in expected.items()
            ):
                raise HTTPException(409, "Identificador de operação já utilizado.")
            return view(existing)
        product = self.get(Product, payload.product_id)
        if not product.is_active or product.individual_tracking:
            raise HTTPException(
                409, "Movimento por quantidade exige produto ativo sem controle individual."
            )
        if payload.from_status == payload.to_status:
            raise HTTPException(422, "Origem e destino devem ser diferentes.")
        if payload.from_status is None and payload.to_status != "DISPONIVEL":
            raise HTTPException(422, "Entradas de estoque devem ser para Disponível.")
        if payload.to_status == "BAIXADO" and payload.from_status in {"RESERVADO", "LOCADO"}:
            raise HTTPException(409, "Libere a reserva ou locação antes da baixa.")
        if payload.from_status == "BAIXADO":
            raise HTTPException(409, "Estoque baixado não pode retornar por transferência.")
        if payload.from_status and self.balances(product)[payload.from_status] < quantity:
            raise HTTPException(409, "Saldo insuficiente. O estoque não pode ficar negativo.")
        if self.balances(product)[payload.to_status] + quantity > 999999999000:
            raise HTTPException(422, "Saldo excede o limite permitido.")
        movement = StockMovement(
            **values, quantity_milli=quantity, request_key=key, created_by=self.actor.id
        )
        self.db.add(movement)
        self.db.flush()
        self.audit("stock.moved", movement)
        return view(movement)

    def equipment_status(self, record_id, payload):
        row = self.get(Equipment, record_id)
        self.version(row, payload.version)
        product = self.get(Product, row.product_id)
        if not product.is_active:
            raise HTTPException(409, "Reative o produto antes de movimentar a unidade.")
        if row.status == "BAIXADO" or row.status == payload.status:
            raise HTTPException(
                409, "Transição inválida; unidades baixadas preservam seu histórico."
            )
        if payload.status == "BAIXADO" and row.status in {"RESERVADO", "LOCADO"}:
            raise HTTPException(409, "Libere a reserva ou locação antes de baixar a unidade.")
        before = view(row)
        movement = StockMovement(
            product_id=row.product_id,
            equipment_id=row.id,
            from_status=row.status,
            to_status=payload.status,
            quantity_milli=1000,
            reason=payload.reason,
            created_by=self.actor.id,
        )
        row.status = payload.status
        row.version += 1
        row.updated_at = int(time.time())
        self.db.add(movement)
        self.db.flush()
        self.audit("equipment.status_changed", row, before)
        self.audit("stock.moved", movement)
        return view(row)

    def price(self, payload, prior_id=None, retire=False):
        if prior_id:
            prior = self.get(Price, prior_id)
            latest = self.db.scalar(
                select(Price.id)
                .where(
                    Price.product_id == prior.product_id,
                    Price.period == prior.period,
                    Price.effective_date == prior.effective_date,
                )
                .order_by(Price.id.desc())
                .limit(1)
            )
            if latest != prior.id:
                raise HTTPException(409, "Preço já possui versão posterior. Atualize o histórico.")
        if retire:
            if prior.amount_cents is None:
                raise HTTPException(409, "Esta versão já está desativada.")
            product_id, period, effective = prior.product_id, prior.period, prior.effective_date
            amount = None
        else:
            product_id, period = payload.product_id, payload.period
            effective, amount = payload.effective_date.isoformat(), int(payload.amount * 100)
            if prior_id and (product_id, period, effective) != (
                prior.product_id,
                prior.period,
                prior.effective_date,
            ):
                raise HTTPException(
                    422, "Revisão deve manter produto, período e início de vigência."
                )
        product = self.get(Product, product_id)
        if not product.is_active:
            raise HTTPException(409, "Preço exige produto ativo.")
        if not prior_id:
            prior_id = self.db.scalar(
                select(Price.id)
                .where(
                    Price.product_id == product_id,
                    Price.period == period,
                    Price.effective_date == effective,
                )
                .order_by(Price.id.desc())
                .limit(1)
            )
        row = Price(
            product_id=product_id,
            period=period,
            effective_date=effective,
            amount_cents=amount,
            reason=payload.reason,
            supersedes_id=prior_id,
            created_by=self.actor.id,
        )
        self.db.add(row)
        self.db.flush()
        self.audit("price.retired" if retire else "price.published", row)
        return view(row)

    def effective_price(self, product_id, period, at: date):
        product = self.get(Product, product_id)
        if not product.is_active:
            raise HTTPException(409, "Produto desativado.")
        row = self.db.scalar(
            select(Price)
            .where(
                Price.product_id == product_id,
                Price.period == period,
                Price.effective_date <= at.isoformat(),
            )
            .order_by(Price.effective_date.desc(), Price.id.desc())
            .limit(1)
        )
        if row is None or row.amount_cents is None:
            raise HTTPException(404, "Não há preço vigente para o produto, período e data.")
        return view(row)


def page(
    db, model, q="", active=None, product_id=None, status=None, period=None, offset=0, limit=20
):
    stmt = select(model)
    if model is Customer:
        columns = (Customer.legal_name, Customer.trade_name, Customer.document, Customer.email)
    elif model is Product:
        columns = (Product.code, Product.name, Product.category)
    elif model is Equipment:
        columns = (Equipment.code, Equipment.asset_tag, Equipment.serial_number, Equipment.brand)
    else:
        columns = ()
    if q and columns:
        stmt = stmt.where(or_(*(column.icontains(q, autoescape=True) for column in columns)))
    if active is not None and model in (Customer, Product):
        stmt = stmt.where(model.is_active == active)
    if product_id is not None:
        stmt = stmt.where(model.product_id == product_id)
    if status is not None and model is Equipment:
        stmt = stmt.where(model.status == status)
    if period is not None and model is Price:
        stmt = stmt.where(model.period == period)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = list(db.scalars(stmt.order_by(model.id.desc()).offset(offset).limit(limit)))
    return items, total
