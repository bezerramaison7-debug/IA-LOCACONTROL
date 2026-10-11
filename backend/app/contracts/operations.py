"""Withdrawal, return and renewal. Each call is one atomic unit with stock and audit."""

import time

from fastapi import HTTPException
from sqlalchemy import func, select

from app.contracts.models import (
    Contract,
    ContractItem,
    ItemUnit,
    RentalReturn,
    ReturnItem,
    Withdrawal,
    WithdrawalItem,
)
from app.contracts.service import STATUS_LABELS, ContractService, balance, quantities
from app.masters.models import Equipment, Product, StockMovement
from app.masters.service import MasterService
from app.quotes import calc
from app.quotes.service import PERIOD_LABELS

PRICE_OPTION_LABELS = {
    "ANTERIORES": "preços anteriores mantidos",
    "ATUAIS": "preços atuais da tabela",
    "NEGOCIADOS": "preços negociados",
}


class OperationService:
    def __init__(self, db, actor, soon_days: int = 3):
        self.db = db
        self.actor = actor
        self.contracts = ContractService(db, actor, soon_days)
        self.masters = MasterService(db, actor)

    # ---- helpers -------------------------------------------------------------------

    def replay(self, model, key: str, contract_id: int):
        """Same request key from the same user and contract is a repeat, not a new operation."""
        existing = self.db.scalar(select(model).where(model.request_key == key))
        if existing is None:
            return False
        if existing.contract_id != contract_id or existing.created_by != self.actor.id:
            raise HTTPException(409, "Identificador de operação já utilizado.")
        return True

    def item(self, row: Contract, item_id: int) -> ContractItem:
        for item in row.items:
            if item.id == item_id:
                return item
        raise HTTPException(404, "Item não pertence a este contrato.")

    def move(self, item: ContractItem, equipment, source, target, quantity_milli, reason):
        movement = StockMovement(
            product_id=item.product_id,
            equipment_id=equipment.id if equipment else None,
            from_status=source,
            to_status=target,
            quantity_milli=quantity_milli,
            reason=reason,
            created_by=self.actor.id,
        )
        if equipment:
            equipment.status = target
            equipment.version += 1
            equipment.updated_at = int(time.time())
        self.db.add(movement)
        self.db.flush()
        self.masters.audit("stock.moved", movement)

    def equipment(self, equipment_id: int, item: ContractItem) -> Equipment:
        equipment = self.db.get(Equipment, equipment_id)
        if equipment is None:
            raise HTTPException(404, "Equipamento não encontrado.")
        if equipment.product_id != item.product_id:
            raise HTTPException(
                409, f"Equipamento {equipment.code} não é do produto {item.product_code}."
            )
        return equipment

    def held_units(self, item: ContractItem) -> dict:
        return {
            unit.equipment_id: unit
            for unit in self.db.scalars(
                select(ItemUnit).where(
                    ItemUnit.contract_item_id == item.id, ItemUnit.state == "EM_POSSE"
                )
            )
        }

    def whole_units(self, item: ContractItem, quantity_milli: int) -> int:
        if quantity_milli % 1000:
            raise HTTPException(
                422, f"{item.product_code} é controlado por unidade: use quantidade inteira."
            )
        return quantity_milli // 1000

    # ---- withdrawal ----------------------------------------------------------------

    def withdraw(self, contract_id: int, payload) -> dict:
        key = str(payload.request_key)
        if self.replay(Withdrawal, key, contract_id):
            return self.contracts.detail(contract_id)
        row = self.contracts.get(contract_id)
        if row.status not in {"AGUARDANDO_RETIRADA", "ATIVO"}:
            raise HTTPException(409, f"Contrato {STATUS_LABELS[row.status]} não permite retirada.")
        before = self.contracts.view(row)
        moved = quantities(self.db, row.items)
        withdrawal = Withdrawal(
            contract_id=row.id,
            occurred_on=payload.occurred_on.isoformat(),
            notes=payload.notes,
            request_key=key,
            created_by=self.actor.id,
        )
        reason = f"Retirada do contrato {row.number}"
        for line in payload.items:
            item = self.item(row, line.contract_item_id)
            quantity_milli = int(line.quantity * 1000)
            remaining = balance(item, moved[item.id])["to_withdraw"]
            if quantity_milli > remaining:
                raise HTTPException(
                    409,
                    f"{item.product_code}: a quantidade supera o saldo a retirar "
                    f"({calc.quantity(remaining)}).",
                )
            if item.individual_tracking:
                count = self.whole_units(item, quantity_milli)
                if len(line.equipment_ids) != count:
                    raise HTTPException(
                        422,
                        f"{item.product_code}: informe uma unidade física por unidade retirada.",
                    )
                for equipment_id in line.equipment_ids:
                    equipment = self.equipment(equipment_id, item)
                    if equipment.status != "DISPONIVEL":
                        raise HTTPException(
                            409, f"Equipamento {equipment.code} não está disponível."
                        )
                    self.move(item, equipment, "DISPONIVEL", "LOCADO", 1000, reason)
                    self.db.add(ItemUnit(contract_item_id=item.id, equipment_id=equipment.id))
                    withdrawal.items.append(
                        WithdrawalItem(
                            contract_item_id=item.id, quantity_milli=1000, equipment_id=equipment.id
                        )
                    )
            else:
                if line.equipment_ids:
                    raise HTTPException(
                        422, f"{item.product_code} é controlado por quantidade, sem unidade física."
                    )
                product = self.db.get(Product, item.product_id)
                if self.masters.balances(product)["DISPONIVEL"] < quantity_milli:
                    raise HTTPException(
                        409, f"{item.product_code}: saldo disponível insuficiente para a retirada."
                    )
                self.move(item, None, "DISPONIVEL", "LOCADO", quantity_milli, reason)
                withdrawal.items.append(
                    WithdrawalItem(contract_item_id=item.id, quantity_milli=quantity_milli)
                )
        self.db.add(withdrawal)
        row.status = "ATIVO"
        self.contracts.touch(row)
        self.contracts.refresh_state(row)
        self.contracts.event(
            row, "RETIRADA", f"Retirada registrada em {payload.occurred_on.strftime('%d/%m/%Y')}."
        )
        self.contracts.audit("contract.withdrawn", row, before)
        return self.contracts.view(row)

    # ---- return --------------------------------------------------------------------

    def give_back(self, contract_id: int, payload) -> dict:
        key = str(payload.request_key)
        if self.replay(RentalReturn, key, contract_id):
            return self.contracts.detail(contract_id)
        row = self.contracts.get(contract_id)
        if row.status != "ATIVO":
            raise HTTPException(
                409, f"Contrato {STATUS_LABELS[row.status]} não possui itens a devolver."
            )
        before = self.contracts.view(row)
        moved = quantities(self.db, row.items)
        outstanding = {item.id: balance(item, moved[item.id])["outstanding"] for item in row.items}
        returned = RentalReturn(
            contract_id=row.id,
            occurred_on=payload.occurred_on.isoformat(),
            notes=payload.notes,
            request_key=key,
            created_by=self.actor.id,
        )
        reason = f"Devolução do contrato {row.number}"
        for line in payload.items:
            item = self.item(row, line.contract_item_id)
            quantity_milli = int(line.quantity * 1000)
            if quantity_milli > outstanding[item.id]:
                raise HTTPException(
                    409,
                    f"{item.product_code}: a quantidade devolvida supera a quantidade pendente "
                    f"({calc.quantity(outstanding[item.id])}).",
                )
            outstanding[item.id] -= quantity_milli
            equipment = None
            if item.individual_tracking:
                if line.equipment_id is None or quantity_milli != 1000:
                    raise HTTPException(
                        422, f"{item.product_code}: devolva uma unidade física por linha."
                    )
                equipment = self.equipment(line.equipment_id, item)
                unit = self.held_units(item).get(equipment.id)
                if unit is None:
                    raise HTTPException(
                        409, f"Equipamento {equipment.code} não está com o cliente neste contrato."
                    )
                unit.state = "DEVOLVIDO"
            elif line.equipment_id is not None:
                raise HTTPException(
                    422, f"{item.product_code} é controlado por quantidade, sem unidade física."
                )
            self.move(item, equipment, "LOCADO", line.destination, quantity_milli, reason)
            returned.items.append(
                ReturnItem(
                    contract_item_id=item.id,
                    quantity_milli=quantity_milli,
                    equipment_id=equipment.id if equipment else None,
                    condition=line.condition,
                    destination=line.destination,
                    notes=line.notes,
                )
            )
        self.db.add(returned)
        self.contracts.touch(row)
        day = payload.occurred_on.strftime("%d/%m/%Y")
        total = not any(outstanding.values())
        self.contracts.event(
            row, "DEVOLUCAO", f"Devolução {'total' if total else 'parcial'} registrada em {day}."
        )
        self.contracts.refresh_state(row)
        self.contracts.audit("contract.returned", row, before)
        return self.contracts.view(row)

    # ---- renewal -------------------------------------------------------------------

    def renewal_price(self, option, line, source: ContractItem, start):
        """Returns (price_id, table_cents, unit_cents) and records nothing implicitly."""
        if option == "ANTERIORES":
            if line.period != source.period:
                raise HTTPException(
                    422,
                    f"{source.product_code}: manter preços anteriores exige o mesmo período "
                    f"({PERIOD_LABELS[source.period]}).",
                )
            if (
                line.unit_price is not None
                and int(line.unit_price * 100) != source.unit_price_cents
            ):
                raise HTTPException(
                    422, "Para informar outro valor, escolha a opção de preços negociados."
                )
            return source.price_id, source.table_price_cents, source.unit_price_cents
        product = self.db.get(Product, source.product_id)
        price = self.contracts.pricing.table_price(product, line.period, start)
        if price is None:
            raise HTTPException(
                409,
                f"Não há preço {PERIOD_LABELS[line.period]} vigente para {source.product_code} "
                f"em {start.strftime('%d/%m/%Y')}.",
            )
        if option == "ATUAIS":
            if line.unit_price is not None and int(line.unit_price * 100) != price.amount_cents:
                raise HTTPException(
                    422, "Para informar outro valor, escolha a opção de preços negociados."
                )
            return price.id, price.amount_cents, price.amount_cents
        if line.unit_price is None:
            raise HTTPException(
                422, f"{source.product_code}: informe o preço negociado da renovação."
            )
        unit = int(line.unit_price * 100)
        if unit != price.amount_cents and not self.contracts.pricing.can_negotiate:
            raise HTTPException(403, "Você não tem permissão para alterar o preço de tabela.")
        return price.id, price.amount_cents, unit

    def renew(self, contract_id: int, payload) -> dict:
        row = self.contracts.get(contract_id)
        self.contracts.version(row, payload.version)
        if row.status != "ATIVO":
            raise HTTPException(409, f"Contrato {STATUS_LABELS[row.status]} não pode ser renovado.")
        customer = self.contracts.pricing.customer(row.customer_id)
        before = self.contracts.view(row)
        moved = quantities(self.db, row.items)
        renewal = Contract(
            base_number=row.base_number,
            # The unique (base_number, renewal_number) constraint is the final guard.
            renewal_number=(
                self.db.scalar(
                    select(func.max(Contract.renewal_number)).where(
                        Contract.base_number == row.base_number
                    )
                )
                + 1
            ),
            root_id=row.chain_id,
            previous_id=row.id,
            customer_id=customer.id,
            customer_snapshot=self.contracts.pricing.customer_snapshot(customer),
            origin="RENOVACAO",
            price_option=payload.price_option,
            status="ATIVO",
            start_date=payload.start_date.isoformat(),
            notes=payload.notes,
            created_by=self.actor.id,
        )
        items, transfers = [], []
        for position, line in enumerate(payload.items, 1):
            source = self.item(row, line.source_item_id)
            quantity_milli = int(line.quantity * 1000)
            pending = balance(source, moved[source.id])["outstanding"]
            if quantity_milli > pending:
                raise HTTPException(
                    409,
                    f"{source.product_code}: a quantidade renovada supera a quantidade com o "
                    f"cliente ({calc.quantity(pending)}).",
                )
            units = []
            if source.individual_tracking:
                count = self.whole_units(source, quantity_milli)
                held = self.held_units(source)
                chosen = line.equipment_ids or (list(held) if count == len(held) else [])
                if len(chosen) != count or any(e not in held for e in chosen):
                    raise HTTPException(
                        422,
                        f"{source.product_code}: informe quais unidades serão renovadas.",
                    )
                units = [held[e] for e in chosen]
            price_id, table, unit = self.renewal_price(
                payload.price_option, line, source, payload.start_date
            )
            total = calc.item_total_cents(quantity_milli, unit, line.period_count)
            if total > calc.MAX_CENTS:
                raise HTTPException(422, "Valor do item excede o limite permitido.")
            item = ContractItem(
                position=position,
                product_id=source.product_id,
                product_code=source.product_code,
                product_name=source.product_name,
                description=source.description,
                unit=source.unit,
                individual_tracking=source.individual_tracking,
                quantity_milli=quantity_milli,
                period=line.period,
                period_count=line.period_count,
                price_id=price_id,
                table_price_cents=table,
                unit_price_cents=unit,
                total_cents=total,
                start_date=payload.start_date.isoformat(),
                end_date=calc.end_date(
                    payload.start_date, line.period, line.period_count
                ).isoformat(),
                source_item_id=source.id,
                # Custody moves to the renewal line without touching stock: goods stay out.
                carried_milli=quantity_milli,
            )
            items.append(item)
            transfers.append((item, units))
        self.db.add(renewal)
        self.contracts.apply_items(renewal, items)
        self.db.flush()
        for item, units in transfers:
            for unit in units:
                unit.state = "RENOVADO"
                self.db.add(ItemUnit(contract_item_id=item.id, equipment_id=unit.equipment_id))
        self.contracts.touch(row)
        option = PRICE_OPTION_LABELS[payload.price_option]
        self.contracts.event(row, "RENOVADO", f"Renovado no contrato {renewal.number}.")
        self.contracts.event(
            renewal, "RENOVACAO", f"Renovação {renewal.number} de {row.number}: {option}."
        )
        self.contracts.refresh_state(row, f"Renovado no contrato {renewal.number}.")
        self.contracts.refresh_state(renewal)
        self.contracts.audit("contract.renewed", row, before)
        self.contracts.audit("contract.created", renewal)
        return self.contracts.view(renewal)
