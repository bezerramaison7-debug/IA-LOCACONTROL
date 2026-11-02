# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from test_contracts import act, confirmed, contract_body
from test_operations import call, stock_in, withdrawal
from test_quotes import (  # noqa: F401
    PASSWORD,
    START,
    admin,
    body,
    customer,
    line,
    login,
    post,
    product,
    switch,
)

from app.auth.models import User
from app.auth.service import IdentityService
from app.contracts.models import Contract
from app.persistence.database import build_engine
from app.portal.models import RenewalRequest


def link(client, admin, user_id, customer_id, expected=200):
    switch(client, admin)
    response = client.put(
        f"/api/users/{user_id}/customer", json={"customer_id": customer_id}, headers=admin[1]
    )
    assert response.status_code == expected, response.text
    return response.json()


def active_contract(client, admin, person, item, quantity="2.000"):
    contract = confirmed(client, admin, person, [line(item["id"], quantity, "SEMANAL", 1)])
    lines = [{"contract_item_id": contract["items"][0]["id"], "quantity": quantity}]
    active = call(client, admin, contract["id"], "withdrawals", withdrawal(lines))
    document = client.post(f"/api/contracts/{contract['id']}/documents", json={}, headers=admin[1])
    assert document.status_code == 201
    return active, document.json()


@pytest.fixture
def two_customers(client, admin):
    """Dois clientes, cada um com contrato ativo, documento e orçamento enviado."""
    item = product(client, admin, "AND-1")
    stock_in(client, admin, item["id"], "20.000")
    result = []
    for name, document in (("ana", "52998224725"), ("bruno", "11144477735")):
        person = customer(client, admin, document)
        contract, generated = active_contract(client, admin, person, item)
        quote = post(client, admin, "quotes", body(person["id"], [line(item["id"])]))
        sent = client.post(
            f"/api/quotes/{quote['id']}/send", json={"version": quote["version"]}, headers=admin[1]
        )
        assert sent.status_code == 200
        draft_quote = post(client, admin, "quotes", body(person["id"], [line(item["id"], "1.000")]))
        draft = post(client, admin, "contracts", contract_body(person["id"], [line(item["id"])]))
        result.append(
            {
                "person": person,
                "contract": contract,
                "document": generated,
                "quote": quote,
                "draft_quote": draft_quote,
                "draft": draft,
                "username": name,
            }
        )
    for entry in result:
        entry["auth"] = login(client, entry["username"], "CLIENTE")
        link(client, admin, entry["auth"][0], entry["person"]["id"])
        # Vincular revoga sessões antigas: o cliente entra novamente.
        entry["auth"] = relogin(client, entry["username"])
    return result


def relogin(client, username):
    from test_quotes import HEADERS

    client.cookies.clear()
    response = client.post(
        "/api/auth/login", json={"username": username, "password": PASSWORD}, headers=HEADERS
    )
    assert response.status_code == 200
    with Session(client.app.state.engine) as db:
        user_id = db.scalar(select(User.id).where(User.username == username))
    headers = {**HEADERS, "X-CSRF-Token": response.json()["csrf_token"]}
    return user_id, headers, list(client.cookies.jar)


def test_portal_shows_only_the_linked_customer(client, admin, two_customers):
    ana, bruno = two_customers
    switch(client, ana["auth"])
    dashboard = client.get("/api/portal/dashboard").json()
    assert dashboard["active_contracts"] == 1 and dashboard["rented_items"] == "2.000"
    assert [c["id"] for c in dashboard["next_due"]] == [ana["contract"]["id"]]
    contracts = client.get("/api/portal/contracts").json()["items"]
    assert [c["id"] for c in contracts] == [ana["contract"]["id"]]  # rascunho não aparece
    detail = client.get(f"/api/portal/contracts/{ana['contract']['id']}").json()
    assert detail["items"][0]["outstanding"] == "2.000" and detail["documents"][0]["version"] == 1
    assert "notes" not in detail and "customer" not in detail and "created_by" not in detail
    assert all("created_by" not in event for event in detail["events"])
    equipment = client.get("/api/portal/equipment").json()["items"]
    assert [(e["contract_id"], e["quantity"]) for e in equipment] == [
        (ana["contract"]["id"], "2.000")
    ]
    documents = client.get("/api/portal/documents").json()["items"]
    assert [d["id"] for d in documents] == [ana["document"]["id"]]
    quotes = client.get("/api/portal/quotes").json()["items"]
    assert [q["id"] for q in quotes] == [ana["quote"]["id"]]  # rascunho não aparece
    assert client.get("/api/portal/profile").json()["document"] == ana["person"]["document"]
    own_pdf = client.get(f"/api/portal/documents/{ana['document']['id']}/download")
    assert own_pdf.status_code == 200 and own_pdf.content.startswith(b"%PDF")
    quote_pdf = client.get(f"/api/portal/quotes/{ana['quote']['id']}/pdf")
    assert quote_pdf.status_code == 200 and quote_pdf.content.startswith(b"%PDF")


def test_other_customers_records_answer_not_found(client, admin, two_customers):
    ana, bruno = two_customers
    switch(client, ana["auth"])
    forbidden = [
        f"/api/portal/contracts/{bruno['contract']['id']}",
        f"/api/portal/contracts/{ana['draft']['id']}",  # o próprio rascunho também é interno
        f"/api/portal/documents/{bruno['document']['id']}/download",
        f"/api/portal/quotes/{bruno['quote']['id']}",
        f"/api/portal/quotes/{bruno['quote']['id']}/pdf",
        f"/api/portal/quotes/{ana['draft_quote']['id']}",
        "/api/portal/contracts/99999",
    ]
    for url in forbidden:
        assert client.get(url).status_code == 404, url
    request = {"contract_id": bruno["contract"]["id"], "period": "SEMANAL", "period_count": 1}
    response = client.post("/api/portal/renewal-requests", json=request, headers=ana["auth"][1])
    assert response.status_code == 404
    # O perfil Cliente não alcança nenhuma API interna, nem por chamada direta.
    internal = [
        "/api/contracts",
        f"/api/contracts/{ana['contract']['id']}",
        f"/api/contracts/documents/{ana['document']['id']}/download",
        "/api/quotes",
        "/api/customers",
        f"/api/customers/{ana['person']['id']}/summary",
        "/api/dashboard",
        "/api/reports",
        "/api/renewal-requests",
        "/api/stock",
    ]
    for url in internal:
        assert client.get(url).status_code == 403, url
    client.cookies.clear()
    assert client.get("/api/portal/dashboard").status_code == 401


def test_renewal_request_needs_internal_decision_and_never_renews(client, admin, two_customers):
    ana, bruno = two_customers
    request = {
        "contract_id": ana["contract"]["id"],
        "period": "SEMANAL",
        "period_count": 2,
        "notes": "Obra atrasou",
    }
    switch(client, ana["auth"])
    created = client.post("/api/portal/renewal-requests", json=request, headers=ana["auth"][1])
    assert created.status_code == 201 and created.json()["status"] == "PENDENTE"
    again = client.post("/api/portal/renewal-requests", json=request, headers=ana["auth"][1])
    assert again.status_code == 409
    draft = {**request, "contract_id": ana["draft"]["id"]}
    assert (
        client.post("/api/portal/renewal-requests", json=draft, headers=ana["auth"][1]).status_code
        == 404
    )
    decide = f"/api/renewal-requests/{created.json()['id']}/decide"
    assert (
        client.post(decide, json={"decision": "APROVADA"}, headers=ana["auth"][1]).status_code
        == 403
    )
    switch(client, bruno["auth"])
    assert client.get("/api/portal/renewal-requests").json()["items"] == []
    cancel = f"/api/portal/renewal-requests/{created.json()['id']}/cancel"
    assert client.post(cancel, headers=bruno["auth"][1]).status_code == 404

    switch(client, admin)
    pending = client.get("/api/renewal-requests", params={"status": "PENDENTE"}).json()
    assert pending["total"] == 1 and pending["items"][0]["customer"] == ana["person"]["legal_name"]
    refuse = {"decision": "RECUSADA", "reason": "abc"}
    assert client.post(decide, json=refuse, headers=admin[1]).status_code == 422
    approved = client.post(decide, json={"decision": "APROVADA"}, headers=admin[1])
    assert approved.status_code == 200 and approved.json()["status"] == "APROVADA"
    assert client.post(decide, json={"decision": "APROVADA"}, headers=admin[1]).status_code == 409
    with Session(client.app.state.engine) as db:
        # Aprovar registra a decisão; a renovação continua sendo um ato do funcionário.
        assert (
            db.scalar(
                select(func.count()).select_from(Contract).where(Contract.origin == "RENOVACAO")
            )
            == 0
        )
        assert db.scalar(select(func.count()).select_from(RenewalRequest)) == 1
    switch(client, ana["auth"])
    mine = client.get("/api/portal/renewal-requests").json()["items"]
    assert [(r["status"], r["contract_number"]) for r in mine] == [("APROVADA", "1")]
    assert "requested_by" not in mine[0] and "customer" not in mine[0]
    second = client.post("/api/portal/renewal-requests", json=request, headers=ana["auth"][1])
    assert second.status_code == 201
    cancelled = client.post(
        f"/api/portal/renewal-requests/{second.json()['id']}/cancel", headers=ana["auth"][1]
    )
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELADA"


def test_link_rules_and_session_revocation(client, admin, two_customers):
    ana, bruno = two_customers
    seller = login(client, "vendedor", "COMERCIAL")
    link(client, admin, seller[0], ana["person"]["id"], expected=409)  # só perfil Cliente
    link(client, admin, 9999, ana["person"]["id"], expected=404)
    link(client, admin, ana["auth"][0], 9999, expected=404)
    switch(client, seller)
    denied = client.put(
        f"/api/users/{ana['auth'][0]}/customer", json={"customer_id": None}, headers=seller[1]
    )
    assert denied.status_code == 403
    # Trocar o vínculo derruba a sessão antiga; o novo acesso vê apenas o novo cliente.
    moved = link(client, admin, ana["auth"][0], bruno["person"]["id"])
    assert moved["customer_id"] == bruno["person"]["id"]
    switch(client, ana["auth"])
    assert client.get("/api/portal/dashboard").status_code == 401
    fresh = relogin(client, "ana")
    contracts = client.get("/api/portal/contracts").json()["items"]
    assert [c["id"] for c in contracts] == [bruno["contract"]["id"]]
    assert client.get(f"/api/portal/contracts/{ana['contract']['id']}").status_code == 404
    link(client, admin, fresh[0], None)
    relogin(client, "ana")
    unlinked = client.get("/api/portal/dashboard")
    assert unlinked.status_code == 403 and "vinculada" in unlinked.json()["detail"]
    assert act and START  # helpers kept for parity with the other suites


def test_upgrade_0007_to_head_grants_portal_only_to_clients(migration_config):
    command.upgrade(migration_config, "0007_reports")
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
            roles = db.execute(
                text(
                    "SELECT r.code FROM roles r JOIN role_permissions rp ON rp.role_id = r.id "
                    "JOIN permissions p ON p.id = rp.permission_id WHERE p.code = 'portal.access'"
                )
            ).scalars()
            assert list(roles) == ["CLIENTE"]
        command.downgrade(migration_config, "0007_reports")
        with Session(engine) as db:
            assert db.get(User, user_id).password_hash == original_hash
            assert db.scalar(text("SELECT COUNT(*) FROM permissions")) == 28
    finally:
        engine.dispose()


def test_portal_never_shows_internal_cancel_or_close_reasons(client, admin):
    item = product(client, admin, "AND-1")
    person = customer(client, admin, "52998224725")
    contract = confirmed(client, admin, person, [line(item["id"])])
    act(client, admin, contract, "cancel", "Cliente inadimplente no cadastro de crédito")
    auth = login(client, "ana", "CLIENTE")
    link(client, admin, auth[0], person["id"])
    relogin(client, "ana")
    detail = client.get(f"/api/portal/contracts/{contract['id']}").json()
    texts = [event["description"] for event in detail["events"]]
    assert "Contrato cancelado." in texts
    assert not any("inadimplente" in text for text in texts)
