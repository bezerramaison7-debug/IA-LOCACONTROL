# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
"""Rascunhos automáticos (ADR-024): separados dos dados definitivos, por quem digitou,
recuperáveis depois de reabrir o sistema, com expiração de 7 dias e descarte."""

import time

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from test_contracts import confirmed
from test_quotes import admin, base, line, login, switch  # noqa: F401

from app.auth.models import AuditLog
from app.contracts.models import Contract
from app.drafts.models import FormDraft
from app.drafts.routes import TTL_SECONDS
from app.main import create_app
from app.masters.models import StockMovement

QUOTE = {
    "customer_id": "12",
    "start_date": "2026-11-03",
    "notes": "Ligar antes de entregar",
    "items": [{"product_id": "3", "quantity": "2", "period": "SEMANAL"}],
}


def put(client, auth, kind, scope, payload, version=None, expected=200):
    switch(client, auth)
    response = client.put(
        f"/api/drafts/{kind}/{scope}",
        json={"payload": payload, "base_version": version},
        headers=auth[1],
    )
    assert response.status_code == expected, response.text
    return response.json()


def get(client, auth, kind, scope):
    switch(client, auth)
    response = client.get(f"/api/drafts/{kind}/{scope}")
    assert response.status_code == 200, response.text
    return response.json()["draft"]


def test_draft_is_saved_replaced_recovered_after_restart_and_discarded(client, admin):
    assert get(client, admin, "quote", "new") is None
    saved = put(client, admin, "quote", "new", QUOTE)["draft"]
    assert saved["payload"] == QUOTE
    assert saved["expires_at"] - saved["updated_at"] == TTL_SECONDS == 7 * 24 * 3600
    # Salvar de novo substitui (é seguro repetir o mesmo pedido).
    changed = {**QUOTE, "notes": "Entregar às 8h"}
    put(client, admin, "quote", "new", changed)
    put(client, admin, "quote", "new", changed)
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(FormDraft)) == 1
    listing = client.get("/api/drafts").json()
    assert [(d["kind"], d["scope"]) for d in listing["items"]] == [("quote", "new")]
    assert "payload" not in listing["items"][0] and listing["ttl_days"] == 7

    # Reabrir o sistema (novo processo sobre a mesma base) recupera o rascunho.
    settings = client.app.state.settings
    with TestClient(create_app(settings)) as reopened:
        switch(reopened, admin)
        recovered = reopened.get("/api/drafts/quote/new").json()["draft"]
        assert recovered["payload"] == changed

    switch(client, admin)
    assert client.delete("/api/drafts/quote/new", headers=admin[1]).status_code == 204
    assert client.delete("/api/drafts/quote/new", headers=admin[1]).status_code == 204
    assert get(client, admin, "quote", "new") is None


def test_drafts_belong_to_who_typed_them_and_follow_permissions(client, admin):
    put(client, admin, "quote", "new", QUOTE)
    seller = login(client, "seller", "COMERCIAL")
    assert get(client, seller, "quote", "new") is None  # o rascunho do outro não aparece
    put(client, seller, "quote", "new", {**QUOTE, "notes": "do vendedor"})
    assert get(client, admin, "quote", "new")["payload"] == QUOTE
    # Operação não confirma contrato: não guarda rascunho de contrato nem de renovação.
    operator = login(client, "operator", "OPERACAO")
    put(client, operator, "withdrawal", "7", {"lines": []})
    put(client, operator, "contract", "new", QUOTE, expected=403)
    put(client, operator, "renewal", "7", {}, expected=403)
    switch(client, operator)
    assert client.get("/api/drafts/quote/new").status_code == 403

    for kind, scope in (("pedido", "new"), ("quote", "../x"), ("quote", "novo")):
        switch(client, admin)
        response = client.put(f"/api/drafts/{kind}/{scope}", json={"payload": {}}, headers=admin[1])
        assert response.status_code in (404, 405, 422)
    too_big = put(client, admin, "quote", "new", {"notes": "x" * 200_001}, expected=413)
    assert "grande" in too_big["detail"]
    client.cookies.clear()
    assert client.get("/api/drafts/quote/new").status_code == 401


def test_expired_drafts_are_not_offered_and_are_removed(client, admin):
    put(client, admin, "quote", "new", QUOTE)
    put(client, admin, "contract", "new", QUOTE)
    with Session(client.app.state.engine) as db:
        db.execute(
            update(FormDraft)
            .where(FormDraft.kind == "quote")
            .values(expires_at=int(time.time()) - 1)
        )
        db.commit()
    assert get(client, admin, "quote", "new") is None
    assert [d["kind"] for d in client.get("/api/drafts").json()["items"]] == ["contract"]
    put(client, admin, "return", "1", {"lines": []})  # cada gravação limpa os vencidos
    with Session(client.app.state.engine) as db:
        kinds = sorted(db.scalars(select(FormDraft.kind)))
    assert kinds == ["contract", "return"]


def test_a_draft_never_moves_stock_confirms_contract_or_writes_audit(client, admin, base):
    person, item = base
    contract = confirmed(client, admin, person, [line(item["id"])])
    engine = client.app.state.engine

    def snapshot():
        with Session(engine) as db:
            return (
                db.scalar(select(func.count()).select_from(StockMovement)),
                db.scalar(select(func.count()).select_from(AuditLog)),
                db.get(Contract, contract["id"]).status,
                db.get(Contract, contract["id"]).version,
            )

    before = snapshot()
    scope = str(contract["id"])
    payload = {"quantities": {str(contract["items"][0]["id"]): "2"}, "date": "2026-11-03"}
    put(client, admin, "withdrawal", scope, payload, contract["version"])
    put(client, admin, "return", scope, {"lines": [{"quantity": "2"}]}, contract["version"])
    put(client, admin, "renewal", scope, {"option": "TABELA"}, contract["version"])
    put(client, admin, "contract", "new", {"customer_id": str(person["id"])})
    assert snapshot() == before
    draft = get(client, admin, "withdrawal", scope)
    assert draft["base_version"] == contract["version"] and draft["payload"] == payload
    switch(client, admin)
    detail = client.get(f"/api/contracts/{contract['id']}").json()
    assert detail["status"] == "AGUARDANDO_RETIRADA"
    assert all(row["outstanding"] == "0.000" for row in detail["items"])
