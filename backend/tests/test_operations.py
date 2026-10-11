# ruff: noqa: F811 — pytest fixtures imported from test_quotes are test parameters.
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from test_contracts import act, confirmed, contract_body
from test_quotes import (  # noqa: F401 — admin is a fixture reused here
    START,
    TODAY,
    admin,
    customer,
    line,
    login,
    post,
    product,
    switch,
)

from app.auth.models import User
from app.auth.service import IdentityService
from app.contracts.models import Contract, Withdrawal
from app.contracts.operations import OperationService
from app.contracts.schemas import RenewInput, WithdrawInput
from app.masters.models import StockMovement


def stock_in(client, admin, product_id, quantity):
    post(
        client,
        admin,
        "stock/movements",
        {
            "product_id": product_id,
            "quantity": quantity,
            "from_status": None,
            "to_status": "DISPONIVEL",
            "reason": "Entrada inicial",
            "request_key": str(uuid4()),
        },
    )


def balances(client, code):
    rows = client.get("/api/stock", params={"q": code}).json()["items"]
    return next(row["balances"] for row in rows if row["code"] == code)


def unit_status(client, equipment_id):
    return client.get(f"/api/equipment/{equipment_id}").json()["status"]


def call(client, auth, contract_id, path, payload, expected=201):
    switch(client, auth)
    response = client.post(f"/api/contracts/{contract_id}/{path}", json=payload, headers=auth[1])
    assert response.status_code == expected, response.text
    return response.json()


def withdrawal(lines, key=None):
    return {"occurred_on": START, "request_key": key or str(uuid4()), "items": lines}


def returning(lines, key=None):
    return {"occurred_on": START, "request_key": key or str(uuid4()), "items": lines}


def by_code(contract, code):
    return next(item for item in contract["items"] if item["product_code"] == code)


@pytest.fixture
def world(client, admin):
    """Cliente, produto por quantidade com 10 em estoque e produto com 2 unidades físicas."""
    person = customer(client, admin)
    scaffold = product(client, admin, "AND-1")
    stock_in(client, admin, scaffold["id"], "10.000")
    generator = product(client, admin, "GER-1", individual=True)
    units = [
        post(client, admin, "equipment", {"product_id": generator["id"], "code": code})
        for code in ("GER-A", "GER-B")
    ]
    return person, scaffold, generator, units


def test_full_cycle_withdraw_renew_partial_return_renew_total_return(client, admin, world):
    person, scaffold, generator, units = world
    first, second = units
    draft = post(
        client,
        admin,
        "contracts",
        contract_body(
            person["id"],
            [
                line(scaffold["id"], "6.000", "SEMANAL", 1),
                line(generator["id"], "2.000", "DIARIA", 5),
            ],
        ),
    )
    and_item, ger_item = by_code(draft, "AND-1")["id"], by_code(draft, "GER-1")["id"]
    lines = [
        {"contract_item_id": and_item, "quantity": "4.000"},
        {"contract_item_id": ger_item, "quantity": "1.000", "equipment_ids": [first["id"]]},
    ]
    call(client, admin, draft["id"], "withdrawals", withdrawal(lines), expected=409)  # rascunho
    act(client, admin, draft, "confirm")

    key = str(uuid4())
    active = call(client, admin, draft["id"], "withdrawals", withdrawal(lines, key))
    assert (
        active["status"] == "ATIVO" and active["due_date"] == by_code(active, "GER-1")["end_date"]
    )
    assert by_code(active, "AND-1")["outstanding"] == "4.000"
    assert by_code(active, "AND-1")["to_withdraw"] == "2.000"
    assert balances(client, "AND-1")["DISPONIVEL"] == "6.000"
    assert balances(client, "AND-1")["LOCADO"] == "4.000"
    assert unit_status(client, first["id"]) == "LOCADO"
    # Reenvio da mesma operação não movimenta estoque de novo.
    call(client, admin, draft["id"], "withdrawals", withdrawal(lines, key))
    assert balances(client, "AND-1")["LOCADO"] == "4.000"
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Withdrawal)) == 1
    too_many = [{"contract_item_id": and_item, "quantity": "3.000"}]
    call(client, admin, draft["id"], "withdrawals", withdrawal(too_many), expected=409)
    taken = [{"contract_item_id": ger_item, "quantity": "1.000", "equipment_ids": [first["id"]]}]
    call(client, admin, draft["id"], "withdrawals", withdrawal(taken), expected=409)
    rest = [
        {"contract_item_id": and_item, "quantity": "2.000"},
        {"contract_item_id": ger_item, "quantity": "1.000", "equipment_ids": [second["id"]]},
    ]
    active = call(client, admin, draft["id"], "withdrawals", withdrawal(rest))
    assert by_code(active, "AND-1")["to_withdraw"] == "0.000"
    act(client, admin, active, "cancel", "Tentativa indevida", expected=409)

    # Primeira renovação: parte dos andaimes e os dois geradores, mantendo os preços.
    renew = {
        "version": active["version"],
        "start_date": active["due_date"],
        "price_option": "ANTERIORES",
        "items": [
            {
                "source_item_id": and_item,
                "quantity": "4.000",
                "period": "SEMANAL",
                "period_count": 2,
            },
            {
                "source_item_id": ger_item,
                "quantity": "2.000",
                "period": "DIARIA",
                "period_count": 3,
            },
        ],
    }
    one = call(client, admin, draft["id"], "renew", renew)
    assert one["number"] == "1.1" and one["status"] == "ATIVO" and one["origin"] == "RENOVACAO"
    assert one["price_option"] == "ANTERIORES" and one["previous_id"] == draft["id"]
    assert by_code(one, "AND-1")["outstanding"] == "4.000"
    assert by_code(one, "AND-1")["to_withdraw"] == "0.000"
    assert by_code(one, "AND-1")["total"] == "3120.00"  # 4 × 390,00 × 2
    assert sorted(u["code"] for u in by_code(one, "GER-1")["units"]) == ["GER-A", "GER-B"]
    assert balances(client, "AND-1")["LOCADO"] == "6.000"  # renovar não mexe no estoque
    original = client.get(f"/api/contracts/{draft['id']}").json()
    assert original["status"] == "ATIVO" and by_code(original, "AND-1")["outstanding"] == "2.000"
    assert by_code(original, "AND-1")["renewed"] == "4.000"
    assert by_code(original, "GER-1")["outstanding"] == "0.000"
    call(client, admin, draft["id"], "renew", renew, expected=409)  # versão antiga

    # Devolução parcial na renovação: 1 andaime bom e o gerador A avariado.
    one_and, one_ger = by_code(one, "AND-1")["id"], by_code(one, "GER-1")["id"]
    partial = [
        {"contract_item_id": one_and, "quantity": "1.000", "condition": "BOM"},
        {
            "contract_item_id": one_ger,
            "quantity": "1.000",
            "equipment_id": first["id"],
            "condition": "AVARIADO",
            "notes": "Motor falhando",
        },
    ]
    after = call(client, admin, one["id"], "returns", returning(partial))
    assert after["status"] == "ATIVO" and by_code(after, "AND-1")["outstanding"] == "3.000"
    assert balances(client, "AND-1")["DISPONIVEL"] == "5.000"
    assert unit_status(client, first["id"]) == "MANUTENCAO"
    excess = [{"contract_item_id": one_and, "quantity": "3.001", "condition": "BOM"}]
    call(client, admin, one["id"], "returns", returning(excess), expected=409)
    again = [
        {
            "contract_item_id": one_ger,
            "quantity": "1.000",
            "equipment_id": first["id"],
            "condition": "BOM",
        }
    ]
    call(client, admin, one["id"], "returns", returning(again), expected=409)
    wrong = [
        {
            "contract_item_id": one_and,
            "quantity": "1.000",
            "condition": "AVARIADO",
            "destination": "DISPONIVEL",
        }
    ]
    call(client, admin, one["id"], "returns", returning(wrong), expected=422)

    # Os 2 andaimes que ficaram no contrato original voltam: ele se encerra sozinho.
    left = [{"contract_item_id": and_item, "quantity": "2.000", "condition": "BOM"}]
    closed = call(client, admin, draft["id"], "returns", returning(left))
    assert closed["status"] == "ENCERRADO" and closed["due_date"] is None

    # Segunda renovação com preço negociado; a primeira se encerra por ter sido renovada.
    current = client.get(f"/api/contracts/{one['id']}").json()
    renew_two = {
        "version": current["version"],
        "start_date": current["due_date"],
        "price_option": "NEGOCIADOS",
        "items": [
            {
                "source_item_id": one_and,
                "quantity": "3.000",
                "period": "SEMANAL",
                "period_count": 1,
                "unit_price": "300.00",
            },
            {
                "source_item_id": one_ger,
                "quantity": "1.000",
                "period": "DIARIA",
                "period_count": 2,
                "unit_price": "90.00",
            },
        ],
    }
    two = call(client, admin, one["id"], "renew", renew_two)
    assert two["number"] == "1.2" and by_code(two, "AND-1")["total"] == "900.00"
    assert by_code(two, "AND-1")["negotiated"] is True
    assert [u["code"] for u in by_code(two, "GER-1")["units"]] == ["GER-B"]
    assert client.get(f"/api/contracts/{one['id']}").json()["status"] == "ENCERRADO"

    final = [
        {"contract_item_id": by_code(two, "AND-1")["id"], "quantity": "3.000", "condition": "BOM"},
        {
            "contract_item_id": by_code(two, "GER-1")["id"],
            "quantity": "1.000",
            "equipment_id": second["id"],
            "condition": "BOM",
        },
    ]
    done = call(client, admin, two["id"], "returns", returning(final))
    assert done["status"] == "ENCERRADO"
    assert [(c["number"], c["status"]) for c in done["chain"]] == [
        ("1", "ENCERRADO"),
        ("1.1", "ENCERRADO"),
        ("1.2", "ENCERRADO"),
    ]
    kinds = [event["kind"] for event in done["events"]]
    assert kinds[:3] == ["CRIADO", "CONFIRMADO", "RETIRADA"]
    assert kinds.count("RENOVACAO") == 2 and kinds.count("DEVOLUCAO") == 3
    assert kinds.count("ENCERRADO") == 3 and kinds[-1] == "ENCERRADO"
    stock = balances(client, "AND-1")
    assert stock["DISPONIVEL"] == "10.000" and stock["LOCADO"] == "0.000"
    assert unit_status(client, first["id"]) == "MANUTENCAO"
    assert unit_status(client, second["id"]) == "DISPONIVEL"
    call(client, admin, two["id"], "returns", returning(final), expected=409)  # nada pendente
    call(client, admin, two["id"], "renew", {**renew_two, "version": done["version"]}, expected=409)


def test_renewal_price_options_and_permission(client, admin, world):
    person, scaffold, _generator, _units = world
    contract = confirmed(client, admin, person, [line(scaffold["id"], "2.000", "SEMANAL", 1)])
    item = contract["items"][0]["id"]
    active = call(
        client,
        admin,
        contract["id"],
        "withdrawals",
        withdrawal([{"contract_item_id": item, "quantity": "2.000"}]),
    )
    post(
        client,
        admin,
        "prices",
        {
            "product_id": scaffold["id"],
            "period": "SEMANAL",
            "effective_date": "2026-02-01",
            "amount": "450.00",
            "reason": "Reajuste da tabela",
        },
    )

    def renewal(option, quantity="1.000", period="SEMANAL", unit_price=None, version=None):
        return {
            "version": version or active["version"],
            "start_date": START,
            "price_option": option,
            "items": [
                {
                    "source_item_id": item,
                    "quantity": quantity,
                    "period": period,
                    "period_count": 1,
                    "unit_price": unit_price,
                }
            ],
        }

    call(
        client, admin, contract["id"], "renew", renewal("ANTERIORES", period="DIARIA"), expected=422
    )
    call(client, admin, contract["id"], "renew", renewal("NEGOCIADOS"), expected=422)
    call(client, admin, contract["id"], "renew", renewal("ATUAIS", unit_price="1.00"), expected=422)
    call(client, admin, contract["id"], "renew", renewal("ATUAIS", quantity="2.001"), expected=409)
    seller = login(client, "vendedor", "COMERCIAL")
    call(
        client,
        seller,
        contract["id"],
        "renew",
        renewal("NEGOCIADOS", unit_price="100.00"),
        expected=403,
    )
    current = call(client, seller, contract["id"], "renew", renewal("ATUAIS"))
    assert current["number"] == "1.1" and current["items"][0]["unit_price"] == "450.00"
    assert current["items"][0]["table_price"] == "450.00" and current["price_option"] == "ATUAIS"
    fresh = client.get(f"/api/contracts/{contract['id']}").json()
    previous = call(
        client, admin, contract["id"], "renew", renewal("ANTERIORES", version=fresh["version"])
    )
    assert previous["number"] == "1.2" and previous["items"][0]["unit_price"] == "390.00"
    assert client.get(f"/api/contracts/{contract['id']}").json()["status"] == "ENCERRADO"


def test_due_filters_follow_the_due_date(client, admin, world):
    person, scaffold, _generator, _units = world
    contract = confirmed(client, admin, person, [line(scaffold["id"], "1.000", "SEMANAL", 1)])
    lines = [{"contract_item_id": contract["items"][0]["id"], "quantity": "1.000"}]
    active = call(client, admin, contract["id"], "withdrawals", withdrawal(lines))
    assert active["status"] == "ATIVO"

    def shown(days):
        with Session(client.app.state.engine) as db:
            db.get(Contract, contract["id"]).due_date = (TODAY + timedelta(days=days)).isoformat()
            db.commit()
        status = client.get(f"/api/contracts/{contract['id']}").json()["status"]
        counts = {
            name: client.get("/api/contracts", params={"status": name}).json()["total"]
            for name in ("ATIVO", "VENCENDO", "VENCIDO")
        }
        assert counts[status] == 1 and sum(counts.values()) == 1
        return status

    assert shown(10) == "ATIVO"
    assert shown(3) == "VENCENDO"
    assert shown(0) == "VENCENDO"
    assert shown(-1) == "VENCIDO"


def test_manual_close_when_the_rest_was_never_picked_up(client, admin, world):
    person, scaffold, _generator, _units = world
    contract = confirmed(client, admin, person, [line(scaffold["id"], "5.000", "SEMANAL", 1)])
    item = contract["items"][0]["id"]
    active = call(
        client,
        admin,
        contract["id"],
        "withdrawals",
        withdrawal([{"contract_item_id": item, "quantity": "2.000"}]),
    )
    act(client, admin, active, "close", "Cliente não retirou o restante", expected=409)
    back = call(
        client,
        admin,
        contract["id"],
        "returns",
        returning([{"contract_item_id": item, "quantity": "2.000", "condition": "BOM"}]),
    )
    assert back["status"] == "ATIVO" and back["items"][0]["to_withdraw"] == "3.000"
    closed = act(client, admin, back, "close", "Cliente não retirou o restante")
    assert closed["status"] == "ENCERRADO"
    assert balances(client, "AND-1")["DISPONIVEL"] == "10.000"


def test_stock_shortage_and_wrong_units_are_rejected_atomically(client, admin, world):
    person, scaffold, generator, units = world
    other = product(client, admin, "BET-9", individual=True)
    foreign = post(client, admin, "equipment", {"product_id": other["id"], "code": "BET-X"})
    contract = confirmed(
        client,
        admin,
        person,
        [line(scaffold["id"], "12.000", "SEMANAL", 1), line(generator["id"], "1.000", "DIARIA", 1)],
    )
    and_item, ger_item = by_code(contract, "AND-1")["id"], by_code(contract, "GER-1")["id"]

    def attempt(lines, expected):
        call(client, admin, contract["id"], "withdrawals", withdrawal(lines), expected=expected)

    attempt([{"contract_item_id": and_item, "quantity": "11.000"}], 409)  # só há 10
    attempt([{"contract_item_id": ger_item, "quantity": "1.000"}], 422)  # sem unidade física
    attempt(
        [{"contract_item_id": ger_item, "quantity": "1.000", "equipment_ids": [foreign["id"]]}], 409
    )
    attempt(
        [{"contract_item_id": and_item, "quantity": "1.000", "equipment_ids": [units[0]["id"]]}],
        422,
    )
    attempt([{"contract_item_id": 9999, "quantity": "1.000"}], 404)
    # Linha válida seguida de linha inválida: nada é gravado.
    attempt(
        [
            {"contract_item_id": and_item, "quantity": "5.000"},
            {"contract_item_id": ger_item, "quantity": "1.000", "equipment_ids": [foreign["id"]]},
        ],
        409,
    )
    assert balances(client, "AND-1")["DISPONIVEL"] == "10.000"
    assert client.get(f"/api/contracts/{contract['id']}").json()["status"] == "AGUARDANDO_RETIRADA"


def test_audit_failure_rolls_back_withdrawal_and_stock(client, admin, world, monkeypatch):
    person, scaffold, _generator, _units = world
    contract = confirmed(client, admin, person, [line(scaffold["id"], "2.000", "SEMANAL", 1)])
    lines = [{"contract_item_id": contract["items"][0]["id"], "quantity": "2.000"}]
    with Session(client.app.state.engine) as db:
        movements = db.scalar(select(func.count()).select_from(StockMovement))

    def fail(*_args, **_kwargs):
        raise SQLAlchemyError("fixture audit failure")

    monkeypatch.setattr(IdentityService, "audit", fail)
    call(client, admin, contract["id"], "withdrawals", withdrawal(lines), expected=503)
    monkeypatch.undo()
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(StockMovement)) == movements
        assert db.scalar(select(func.count()).select_from(Withdrawal)) == 0
    assert balances(client, "AND-1")["DISPONIVEL"] == "10.000"


def run(client, admin, work):
    with Session(client.app.state.engine) as db:
        db.execute(text("BEGIN IMMEDIATE"))
        try:
            work(OperationService(db, db.get(User, admin[0])))
            db.commit()
            return 201
        except HTTPException as error:
            db.rollback()
            return error.status_code


def test_concurrent_withdrawals_cannot_take_the_same_stock(client, admin, world):
    person, scaffold, _generator, _units = world
    contracts = [
        confirmed(client, admin, person, [line(scaffold["id"], "6.000", "SEMANAL", 1)])
        for _ in range(2)
    ]
    barrier = Barrier(2)

    def take(contract):
        payload = WithdrawInput(
            **withdrawal([{"contract_item_id": contract["items"][0]["id"], "quantity": "6.000"}])
        )
        barrier.wait()
        return run(client, admin, lambda service: service.withdraw(contract["id"], payload))

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(take, contracts)) == [201, 409]
    stock = balances(client, "AND-1")
    assert stock["DISPONIVEL"] == "4.000" and stock["LOCADO"] == "6.000"


def test_concurrent_renewals_create_a_single_next_number(client, admin, world):
    person, scaffold, _generator, _units = world
    contract = confirmed(client, admin, person, [line(scaffold["id"], "2.000", "SEMANAL", 1)])
    item = contract["items"][0]["id"]
    active = call(
        client,
        admin,
        contract["id"],
        "withdrawals",
        withdrawal([{"contract_item_id": item, "quantity": "2.000"}]),
    )
    barrier = Barrier(2)

    def renew(_index):
        payload = RenewInput(
            version=active["version"],
            start_date=START,
            price_option="ANTERIORES",
            items=[
                {
                    "source_item_id": item,
                    "quantity": "2.000",
                    "period": "SEMANAL",
                    "period_count": 1,
                }
            ],
        )
        barrier.wait()
        return run(client, admin, lambda service: service.renew(contract["id"], payload))

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(renew, [1, 2])) == [201, 409]
    chain = client.get(f"/api/contracts/{contract['id']}").json()["chain"]
    assert [c["number"] for c in chain] == ["1", "1.1"]


def test_manual_stock_edits_cannot_contradict_contract_custody(client, admin, world):
    person, scaffold, generator, units = world
    contract = confirmed(
        client,
        admin,
        person,
        [line(scaffold["id"], "4.000", "SEMANAL", 1), line(generator["id"], "1.000", "DIARIA", 1)],
    )
    call(
        client,
        admin,
        contract["id"],
        "withdrawals",
        withdrawal(
            [
                {"contract_item_id": by_code(contract, "AND-1")["id"], "quantity": "4.000"},
                {
                    "contract_item_id": by_code(contract, "GER-1")["id"],
                    "quantity": "1.000",
                    "equipment_ids": [units[0]["id"]],
                },
            ]
        ),
    )

    def manual(quantity, source, target):
        body = {
            "product_id": scaffold["id"],
            "quantity": quantity,
            "from_status": source,
            "to_status": target,
            "reason": "Ajuste manual de estoque",
            "request_key": str(uuid4()),
        }
        return client.post("/api/stock/movements", json=body, headers=admin[1])

    blocked = manual("1.000", "LOCADO", "DISPONIVEL")
    assert blocked.status_code == 409 and "contrato" in blocked.json()["detail"]
    # Locação lançada à mão, fora de contrato, continua ajustável pelo estoque.
    assert manual("2.000", "DISPONIVEL", "LOCADO").status_code == 201
    assert manual("3.000", "LOCADO", "DISPONIVEL").status_code == 409
    assert manual("2.000", "LOCADO", "DISPONIVEL").status_code == 201
    unit = client.get(f"/api/equipment/{units[0]['id']}").json()
    change = {"version": unit["version"], "status": "DISPONIVEL", "reason": "Ajuste manual"}
    held = client.post(f"/api/equipment/{unit['id']}/status", json=change, headers=admin[1])
    assert held.status_code == 409 and "contrato 1" in held.json()["detail"]
    free = client.get(f"/api/equipment/{units[1]['id']}").json()
    change = {"version": free["version"], "status": "MANUTENCAO", "reason": "Revisão preventiva"}
    assert (
        client.post(
            f"/api/equipment/{free['id']}/status", json=change, headers=admin[1]
        ).status_code
        == 200
    )
    assert balances(client, "AND-1")["LOCADO"] == "4.000"
