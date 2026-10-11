# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
"""Acceptance journey of the 1.0 plan, exercised through the public API only."""

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_backups import backup
from test_contracts import act
from test_operations import balances, by_code, call, returning, stock_in, unit_status, withdrawal
from test_portal import link, relogin
from test_quotes import (  # noqa: F401
    HEADERS,
    PASSWORD,
    START,
    admin,
    body,
    line,
    login,
    post,
    switch,
)

from app.auth.models import AuditLog


def test_official_scenario_from_quote_to_closed_chain_and_recovery(client, admin):
    # 1–2: funcionário cadastra o cliente.
    person = post(
        client,
        admin,
        "customers",
        {
            "person_type": "PJ",
            "legal_name": "Construtora Aceite Ltda",
            "document": "11.222.333/0001-81",
            "addresses": [
                {
                    "street": "Av. Central, 100",
                    "city": "Recife",
                    "state": "PE",
                    "postal_code": "50000000",
                }
            ],
        },
    )
    # 3: produtos, preços e estoque (um por quantidade, um por unidade física).
    scaffold = post(client, admin, "products", {"code": "AND-10", "name": "Andaime", "unit": "UN"})
    mixer = post(
        client,
        admin,
        "products",
        {"code": "BET-400", "name": "Betoneira 400 L", "unit": "UN", "individual_tracking": True},
    )
    for product_id, period, amount in (
        (scaffold["id"], "SEMANAL", "70.00"),
        (mixer["id"], "SEMANAL", "390.00"),
        (mixer["id"], "MENSAL", "980.00"),
    ):
        post(
            client,
            admin,
            "prices",
            {
                "product_id": product_id,
                "period": period,
                "effective_date": "2026-01-01",
                "amount": amount,
                "reason": "Tabela inicial",
            },
        )
    stock_in(client, admin, scaffold["id"], "20.000")
    mixers = [
        post(client, admin, "equipment", {"product_id": mixer["id"], "code": code})
        for code in ("BET-01", "BET-02")
    ]
    # 4–6: o sistema informa disponibilidade e carrega o preço do período.
    pricing = client.get(
        "/api/quotes/pricing",
        params={"product_id": mixer["id"], "period": "SEMANAL", "at": START},
    ).json()
    assert pricing["table_price"] == "390.00" and pricing["available"] == "2.000"
    # 7–8: orçamento gerado e aprovado.
    quote = post(
        client,
        admin,
        "quotes",
        body(
            person["id"],
            [
                line(scaffold["id"], "10.000", "SEMANAL", 2),
                line(mixer["id"], "2.000", "SEMANAL", 2),
            ],
        ),
    )
    assert quote["total"] == "2960.00"  # 10 × 70 × 2 + 2 × 390 × 2
    approved = client.post(
        f"/api/quotes/{quote['id']}/approve", json={"version": quote["version"]}, headers=admin[1]
    ).json()
    # 9: contrato 9193 criado a partir do orçamento.
    numbering = client.put("/api/contracts/numbering", json={"next_number": 9193}, headers=admin[1])
    assert numbering.status_code == 200
    draft = post(
        client,
        admin,
        f"contracts/from-quote/{quote['id']}",
        {"version": approved["version"], "reason": ""},
    )
    assert draft["number"] == "9193" and draft["total"] == "2960.00"
    contract = act(client, admin, draft, "confirm")
    # 10: documento gerado.
    document = client.post(f"/api/contracts/{contract['id']}/documents", json={}, headers=admin[1])
    assert document.status_code == 201
    # 11–13: retirada, estoque atualizado, contrato ativo.
    and_item, bet_item = by_code(contract, "AND-10")["id"], by_code(contract, "BET-400")["id"]
    active = call(
        client,
        admin,
        contract["id"],
        "withdrawals",
        withdrawal(
            [
                {"contract_item_id": and_item, "quantity": "10.000"},
                {
                    "contract_item_id": bet_item,
                    "quantity": "2.000",
                    "equipment_ids": [m["id"] for m in mixers],
                },
            ]
        ),
    )
    assert active["status"] == "ATIVO"
    assert balances(client, "AND-10")["DISPONIVEL"] == "10.000"
    assert balances(client, "AND-10")["LOCADO"] == "10.000"
    assert [unit_status(client, m["id"]) for m in mixers] == ["LOCADO", "LOCADO"]
    # 14: o cliente solicita a renovação pelo portal; o funcionário decide e renova.
    portal_user = login(client, "cliente", "CLIENTE")
    link(client, admin, portal_user[0], person["id"])
    portal_user = relogin(client, "cliente")
    request = client.post(
        "/api/portal/renewal-requests",
        json={"contract_id": contract["id"], "period": "SEMANAL", "period_count": 1},
        headers=portal_user[1],
    )
    assert request.status_code == 201
    switch(client, admin)
    decided = client.post(
        f"/api/renewal-requests/{request.json()['id']}/decide",
        json={"decision": "APROVADA"},
        headers=admin[1],
    )
    assert decided.status_code == 200
    # 15: o sistema cria 9193.1 com todos os itens, mantendo os preços.
    one = call(
        client,
        admin,
        contract["id"],
        "renew",
        {
            "version": active["version"],
            "start_date": active["due_date"],
            "price_option": "ANTERIORES",
            "items": [
                {
                    "source_item_id": and_item,
                    "quantity": "10.000",
                    "period": "SEMANAL",
                    "period_count": 1,
                },
                {
                    "source_item_id": bet_item,
                    "quantity": "2.000",
                    "period": "SEMANAL",
                    "period_count": 1,
                },
            ],
        },
    )
    assert one["number"] == "9193.1"
    assert client.get(f"/api/contracts/{contract['id']}").json()["status"] == "ENCERRADO"
    # 16–17: parte dos equipamentos é devolvida e o estoque acompanha.
    one_and, one_bet = by_code(one, "AND-10")["id"], by_code(one, "BET-400")["id"]
    partial = call(
        client,
        admin,
        one["id"],
        "returns",
        returning(
            [
                {"contract_item_id": one_and, "quantity": "6.000", "condition": "BOM"},
                {
                    "contract_item_id": one_bet,
                    "quantity": "1.000",
                    "equipment_id": mixers[0]["id"],
                    "condition": "BOM",
                },
            ]
        ),
    )
    assert partial["status"] == "ATIVO"
    assert balances(client, "AND-10")["DISPONIVEL"] == "16.000"
    assert unit_status(client, mixers[0]["id"]) == "DISPONIVEL"
    # 18: nova renovação cria 9193.2 com o que ficou, agora mensal pela tabela atual.
    two = call(
        client,
        admin,
        one["id"],
        "renew",
        {
            "version": partial["version"],
            "start_date": partial["due_date"],
            "price_option": "ATUAIS",
            "items": [
                {
                    "source_item_id": one_and,
                    "quantity": "4.000",
                    "period": "SEMANAL",
                    "period_count": 1,
                },
                {
                    "source_item_id": one_bet,
                    "quantity": "1.000",
                    "period": "MENSAL",
                    "period_count": 1,
                },
            ],
        },
    )
    assert two["number"] == "9193.2" and two["total"] == "1260.00"  # 4 × 70 + 1 × 980
    # 19–21: cliente devolve o restante; contrato encerra; tudo volta ao estoque.
    done = call(
        client,
        admin,
        two["id"],
        "returns",
        returning(
            [
                {
                    "contract_item_id": by_code(two, "AND-10")["id"],
                    "quantity": "4.000",
                    "condition": "BOM",
                },
                {
                    "contract_item_id": by_code(two, "BET-400")["id"],
                    "quantity": "1.000",
                    "equipment_id": mixers[1]["id"],
                    "condition": "BOM",
                },
            ]
        ),
    )
    assert [(c["number"], c["status"]) for c in done["chain"]] == [
        ("9193", "ENCERRADO"),
        ("9193.1", "ENCERRADO"),
        ("9193.2", "ENCERRADO"),
    ]
    stock = balances(client, "AND-10")
    assert stock["DISPONIVEL"] == "20.000" and stock["LOCADO"] == "0.000"
    assert [unit_status(client, m["id"]) for m in mixers] == ["DISPONIVEL", "DISPONIVEL"]
    # 22 e 26: histórico consultável e nenhum snapshot sobrescrito.
    original = client.get(f"/api/contracts/{contract['id']}").json()
    assert original["total"] == "2960.00" and original["quote_number"] == quote["number"]
    assert client.get(f"/api/quotes/{quote['id']}").json()["status"] == "CONVERTIDO"
    kinds = [event["kind"] for event in done["events"]]
    for expected in ("CRIADO", "CONFIRMADO", "DOCUMENTO", "RETIRADA", "RENOVACAO", "DEVOLUCAO"):
        assert expected in kinds
    assert kinds.count("ENCERRADO") == 3
    assert (
        client.get(f"/api/contracts/documents/{document.json()['id']}/download").status_code == 200
    )

    # 23: filtros encontram qualquer contrato.
    def found(**params):
        items = client.get("/api/contracts", params=params).json()["items"]
        return sorted(item["number"] for item in items)

    chain = ["9193", "9193.1", "9193.2"]
    assert found(q="9193") == chain and found(q="9193.2") == ["9193.2"]
    assert found(q="11.222.333/0001-81") == chain and found(q="aceite") == chain
    assert found(equipment="BET-02") == chain and found(product="andaime") == chain
    assert found(period="MENSAL") == ["9193.2"] and found(origin="RENOVACAO") == chain[1:]
    assert found(status="ENCERRADO") == chain and found(status="ATIVO") == []
    # 24: dashboard e relatórios mostram a realidade.
    cards = client.get("/api/dashboard").json()["cards"]
    assert cards["active_contracts"] == 0 and cards["rented_items"] == "0.000"
    assert cards["equipment_available"] == 2 and cards["contracted_value"] == "0.00"
    revenue = client.get("/api/reports/contracted_revenue").json()["rows"]
    assert sum(row["contracts"] for row in revenue) == 3
    returns = client.get("/api/reports/returns").json()
    assert returns["total"] == 4
    # Auditoria registra as operações críticas com autor.
    with Session(client.app.state.engine) as db:
        actions = set(db.scalars(select(AuditLog.action)))
    assert {
        "quote.created",
        "quote.approved",
        "quote.converted",
        "contract.created",
        "contract.confirmed",
        "contract.withdrawn",
        "contract.renewed",
        "contract.returned",
        "contract.document_generated",
        "stock.moved",
        "renewal_request.created",
        "renewal_request.decided",
        "portal.link_changed",
    } <= actions
    # 25: backup protege os dados; depois de novas alterações, a restauração os recupera.
    saved = backup(client, admin)
    post(client, admin, "products", {"code": "DEPOIS-1", "name": "Criado depois", "unit": "UN"})
    restored = client.post(
        f"/api/backups/{saved['name']}/restore",
        json={"confirmation": f"RESTAURAR {saved['name']}", "password": PASSWORD},
        headers=admin[1],
    )
    assert restored.status_code == 200, restored.text
    client.cookies.clear()
    again = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    )
    assert again.status_code == 200
    assert client.get("/api/products", params={"q": "DEPOIS"}).json()["total"] == 0
    assert found(q="9193") == chain
    assert (
        client.get(f"/api/contracts/documents/{document.json()['id']}/download").status_code == 200
    )
    assert client.get("/health").json()["status"] == "ok"
