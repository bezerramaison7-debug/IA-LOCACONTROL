# ruff: noqa: F811 — pytest fixtures imported from test_quotes are test parameters.
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from test_quotes import (  # noqa: F401 — admin/base are fixtures reused here
    HEADERS,
    PASSWORD,
    START,
    TODAY,
    admin,
    base,
    body,
    customer,
    line,
    login,
    post,
    product,
    switch,
)

from app.auth.models import AuditLog, User
from app.auth.service import IdentityService
from app.contracts.models import Contract, ContractDocument, ContractTemplate
from app.contracts.schemas import ContractInput
from app.contracts.service import ContractService
from app.persistence.database import build_engine


def contract_body(customer_id, items, **extra):
    return {"customer_id": customer_id, "start_date": START, "items": items, **extra}


def act(client, auth, contract, action, reason="", expected=200):
    switch(client, auth)
    response = client.post(
        f"/api/contracts/{contract['id']}/{action}",
        json={"version": contract["version"], "reason": reason},
        headers=auth[1],
    )
    assert response.status_code == expected, response.text
    return response.json()


def confirmed(client, admin, person, items):
    draft = post(client, admin, "contracts", contract_body(person["id"], items))
    return act(client, admin, draft, "confirm")


def test_direct_contract_numbering_snapshots_and_lifecycle(client, admin, base):
    person, item = base
    first = post(client, admin, "contracts", contract_body(person["id"], [line(item["id"])]))
    assert first["number"] == "1" and first["status"] == "RASCUNHO" and first["origin"] == "DIRETO"
    row = first["items"][0]
    assert (row["table_price"], row["unit_price"], row["total"]) == ("390.00", "390.00", "2340.00")
    assert row["to_withdraw"] == "2.000" and row["outstanding"] == "0.000"
    assert first["total"] == "2340.00" and first["end_date"] == row["end_date"]
    assert first["events"][0]["kind"] == "CRIADO" and first["chain"][0]["number"] == "1"

    numbering = client.put("/api/contracts/numbering", json={"next_number": 9193}, headers=admin[1])
    assert numbering.status_code == 200 and numbering.json()["next_number"] == 9193
    second = post(client, admin, "contracts", contract_body(person["id"], [line(item["id"])]))
    assert second["number"] == "9193" and second["base_number"] == 9193
    low = client.put("/api/contracts/numbering", json={"next_number": 9000}, headers=admin[1])
    assert low.status_code == 409
    assert client.get("/api/contracts/numbering").json()["next_number"] == 9194

    edit = contract_body(
        person["id"], [line(item["id"], "3.000")], notes="Obra B", version=second["version"]
    )
    edited = client.put(f"/api/contracts/{second['id']}", json=edit, headers=admin[1])
    assert edited.status_code == 200 and edited.json()["total"] == "3510.00"
    ready = act(client, admin, edited.json(), "confirm")
    assert ready["status"] == "AGUARDANDO_RETIRADA"
    locked = {**edit, "version": ready["version"]}
    assert (
        client.put(f"/api/contracts/{second['id']}", json=locked, headers=admin[1]).status_code
        == 409
    )
    act(client, admin, ready, "cancel", "abc", expected=422)
    cancelled = act(client, admin, ready, "cancel", "Cliente desistiu da obra")
    assert cancelled["status"] == "CANCELADO"
    act(client, admin, cancelled, "confirm", expected=409)
    listing = client.get("/api/contracts", params={"q": "9193"}).json()
    assert listing["total"] == 1 and listing["items"][0]["status"] == "CANCELADO"
    assert client.get("/api/contracts", params={"status": "RASCUNHO"}).json()["total"] == 1
    with Session(client.app.state.engine) as db:
        actions = set(db.scalars(select(AuditLog.action).where(AuditLog.entity == "contracts")))
        assert {"contract.created", "contract.confirmed", "contract.cancelled"} <= actions


def test_quote_converts_once_and_keeps_its_prices(client, admin, base):
    person, item = base
    quote = post(
        client, admin, "quotes", body(person["id"], [line(item["id"], unit_price="350.00")])
    )
    version = {"version": quote["version"], "reason": ""}
    url = f"/api/contracts/from-quote/{quote['id']}"
    assert client.post(url, json=version, headers=admin[1]).status_code == 409  # não aprovado
    approved = client.post(
        f"/api/quotes/{quote['id']}/approve", json=version, headers=admin[1]
    ).json()
    post(
        client,
        admin,
        "prices",
        {
            "product_id": item["id"],
            "period": "SEMANAL",
            "effective_date": "2026-02-01",
            "amount": "500.00",
            "reason": "Reajuste da tabela",
        },
    )
    version = {"version": approved["version"], "reason": ""}
    contract = post(client, admin, f"contracts/from-quote/{quote['id']}", version)
    assert contract["origin"] == "ORCAMENTO" and contract["quote_number"] == quote["number"]
    assert contract["items"][0]["unit_price"] == "350.00"
    assert contract["items"][0]["table_price"] == "390.00" and contract["total"] == "2100.00"
    converted = client.get(f"/api/quotes/{quote['id']}").json()
    assert converted["status"] == "CONVERTIDO"
    again = {"version": converted["version"], "reason": ""}
    assert client.post(url, json=again, headers=admin[1]).status_code == 409
    cancel = {"version": converted["version"], "reason": "Tentativa indevida"}
    assert (
        client.post(f"/api/quotes/{quote['id']}/cancel", json=cancel, headers=admin[1]).status_code
        == 409
    )
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Contract)) == 1


def test_documents_are_versioned_and_signed_copy_is_never_replaced(client, admin, base):
    person, item = base
    draft = post(client, admin, "contracts", contract_body(person["id"], [line(item["id"])]))
    preview = client.get(f"/api/contracts/{draft['id']}/preview.pdf")
    assert preview.status_code == 200 and preview.content.startswith(b"%PDF")
    documents = f"/api/contracts/{draft['id']}/documents"
    assert client.post(documents, json={}, headers=admin[1]).status_code == 409
    act(client, admin, draft, "confirm")

    first = client.post(documents, json={}, headers=admin[1])
    assert first.status_code == 201 and first.json()["version"] == 1
    second = client.post(documents, json={}, headers=admin[1]).json()
    listed = {
        d["version"]: d["status"]
        for d in client.get(f"/api/contracts/{draft['id']}").json()["documents"]
    }
    assert listed == {1: "SUBSTITUIDO", 2: "GERADO"}
    sign = f"/api/contracts/documents/{second['id']}/sign"
    signed = client.post(sign, json={"notes": "Assinado no balcão"}, headers=admin[1])
    assert signed.status_code == 200 and signed.json()["status"] == "ASSINADO"
    assert client.post(sign, json={}, headers=admin[1]).status_code == 409
    old = f"/api/contracts/documents/{first.json()['id']}/sign"
    assert client.post(old, json={}, headers=admin[1]).status_code == 409

    assert client.post(documents, json={}, headers=admin[1]).status_code == 422
    third = client.post(documents, json={"reason": "Correção do endereço"}, headers=admin[1])
    assert third.status_code == 201 and third.json()["version"] == 3
    listed = {
        d["version"]: d["status"]
        for d in client.get(f"/api/contracts/{draft['id']}").json()["documents"]
    }
    assert listed == {1: "SUBSTITUIDO", 2: "ASSINADO", 3: "GERADO"}

    download = client.get(f"/api/contracts/documents/{second['id']}/download")
    assert download.status_code == 200 and download.content.startswith(b"%PDF")
    assert hashlib.sha256(download.content).hexdigest() == second["checksum"]
    assert "Contrato-1-v2.pdf" in download.headers["content-disposition"]
    with Session(client.app.state.engine) as db:
        stored = db.get(ContractDocument, second["id"]).stored_name
    path = Path(client.app.state.settings.document_directory) / stored
    path.write_bytes(path.read_bytes() + b"tampered")
    assert client.get(f"/api/contracts/documents/{second['id']}/download").status_code == 409
    client.cookies.clear()
    assert client.get(f"/api/contracts/documents/{third.json()['id']}/download").status_code == 401


def test_templates_validate_placeholders_and_keep_history(client, admin, base):
    person, item = base
    listing = client.get("/api/contracts/templates").json()
    assert len(listing["items"]) == 1 and listing["items"][0]["is_provisional"] is True
    assert "contract.number" in listing["fields"] and "items" in listing["blocks"]
    bad = {
        "name": "Contrato oficial",
        "body": "Contrato {{ contract.numero }} de {{ customer.legal_name }}",
    }
    assert client.post("/api/contracts/templates", json=bad, headers=admin[1]).status_code == 422
    inline = {
        "name": "Contrato oficial",
        "body": "Itens da locação: {{ items }} conforme combinado.",
    }
    assert client.post("/api/contracts/templates", json=inline, headers=admin[1]).status_code == 422
    good = {
        "name": "Contrato oficial",
        "body": "# Contrato {{ contract.number }}\n\nCliente {{ customer.legal_name }}.\n\n"
        "{{ items }}\n\n{{ totals }}\n\n{{ signatures }}",
    }
    published = client.post("/api/contracts/templates", json=good, headers=admin[1])
    assert published.status_code == 201 and published.json()["version"] == 1
    again = client.post("/api/contracts/templates", json=good, headers=admin[1]).json()
    assert again["version"] == 2 and again["is_provisional"] is False
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(ContractTemplate)) == 3
        active = list(db.scalars(select(ContractTemplate.id).where(ContractTemplate.is_active)))
        assert active == [again["id"]]
    contract = confirmed(client, admin, person, [line(item["id"])])
    generated = client.post(f"/api/contracts/{contract['id']}/documents", json={}, headers=admin[1])
    assert generated.status_code == 201 and generated.json()["template_id"] == again["id"]
    seller = login(client, "vendedor", "COMERCIAL")
    assert client.post("/api/contracts/templates", json=good, headers=seller[1]).status_code == 403
    assert (
        client.put(
            "/api/contracts/numbering", json={"next_number": 50}, headers=seller[1]
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "role,can_read,can_write,can_operate",
    [
        ("COMERCIAL", True, True, False),
        ("OPERACAO", True, False, True),
        ("FINANCEIRO", True, False, False),
        ("CLIENTE", False, False, False),
    ],
)
def test_contract_roles_are_enforced_by_the_api(
    client, admin, base, role, can_read, can_write, can_operate
):
    person, item = base
    contract = confirmed(client, admin, person, [line(item["id"])])
    worker = login(client, "worker", role)
    assert client.get("/api/contracts").status_code == (200 if can_read else 403)
    assert client.get(f"/api/contracts/{contract['id']}").status_code == (200 if can_read else 403)
    payload = contract_body(person["id"], [line(item["id"])])
    assert client.post("/api/contracts", json=payload, headers=HEADERS).status_code == 403
    created = client.post("/api/contracts", json=payload, headers=worker[1])
    assert created.status_code == (201 if can_write else 403)
    withdrawal = {
        "occurred_on": START,
        "request_key": "7e1f0c1e-6a53-4f0e-9d53-6f2f0a8f6f09",
        "items": [{"contract_item_id": contract["items"][0]["id"], "quantity": "1.000"}],
    }
    response = client.post(
        f"/api/contracts/{contract['id']}/withdrawals", json=withdrawal, headers=worker[1]
    )
    # Quem pode operar chega à regra de estoque (409 por falta de saldo); os demais param em 403.
    assert response.status_code == (409 if can_operate else 403)


def test_concurrent_creation_never_reuses_a_contract_number(client, admin, base):
    person, item = base
    barrier = Barrier(4)

    def create(_index):
        payload = ContractInput(**contract_body(person["id"], [line(item["id"])]))
        barrier.wait()
        with Session(client.app.state.engine) as db:
            db.execute(text("BEGIN IMMEDIATE"))
            result = ContractService(db, db.get(User, admin[0])).save(payload)
            db.commit()
            return result["number"]

    with ThreadPoolExecutor(max_workers=4) as executor:
        numbers = list(executor.map(create, range(4)))
    assert sorted(numbers) == ["1", "2", "3", "4"]


def test_upgrade_0005_to_head_preserves_account_and_seeds_template(migration_config):
    command.upgrade(migration_config, "0005_quotes")
    engine = build_engine(migration_config.attributes["database_url"])
    try:
        with Session(engine) as db:
            user = IdentityService(db, local=True).create_user(
                "existing", "Existing", PASSWORD, ["ADMINISTRADOR"], must_change=False
            )
            original_hash, user_id = user.password_hash, user.id
            db.commit()
        command.upgrade(migration_config, "head")
        command.check(migration_config)
        with Session(engine) as db:
            assert db.get(User, user_id).password_hash == original_hash
            grants = dict(
                db.execute(
                    text(
                        "SELECT r.code, COUNT(*) FROM roles r "
                        "JOIN role_permissions rp ON rp.role_id = r.id "
                        "JOIN permissions p ON p.id = rp.permission_id "
                        "WHERE p.code LIKE 'contracts.%' OR p.code = 'operations.write' "
                        "GROUP BY r.code"
                    )
                ).all()
            )
            assert grants == {"ADMINISTRADOR": 5, "COMERCIAL": 2, "OPERACAO": 2, "FINANCEIRO": 1}
            template = db.scalar(select(ContractTemplate))
            assert template.is_provisional and "{{ contract.number }}" in template.body
        command.downgrade(migration_config, "0005_quotes")
        with Session(engine) as db:
            assert db.get(User, user_id).password_hash == original_hash
            assert db.scalar(text("SELECT COUNT(*) FROM permissions")) == 22
    finally:
        engine.dispose()


def test_today_constant_matches_service_clock():
    # Guards the shared fixtures: contracts and quotes use the same business date.
    assert START == TODAY.isoformat()


def test_template_block_must_be_the_only_placeholder_on_its_line(client, admin):
    mixed = {"name": "Contrato oficial", "body": "Contrato de locação\n\n{{ today }} {{ items }}"}
    assert client.post("/api/contracts/templates", json=mixed, headers=admin[1]).status_code == 422
    double = {"name": "Contrato oficial", "body": "Contrato de locação\n\n{{ items }}{{ totals }}"}
    assert client.post("/api/contracts/templates", json=double, headers=admin[1]).status_code == 422
    assert len(client.get("/api/contracts/templates").json()["items"]) == 1
