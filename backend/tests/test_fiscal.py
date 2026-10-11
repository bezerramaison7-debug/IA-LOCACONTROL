# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_contracts import confirmed
from test_quotes import START, admin, base, customer, line, login, post, switch  # noqa: F401

from app.core.config import Settings
from app.fiscal.fake import NOTICE, FakeFiscalProvider
from app.fiscal.models import FiscalDocument, FiscalEvent
from app.fiscal.provider import EmissionRequest, build_provider


def fiscal_body(customer_id, contract_id=None, description="Locação de equipamentos", **extra):
    return {
        "customer_id": customer_id,
        "contract_id": contract_id,
        "period_start": START,
        "period_end": START,
        "amount": "2340.00",
        "description": description,
        "request_key": str(uuid4()),
        **extra,
    }


def action(client, auth, document, name, reason="", expected=200):
    switch(client, auth)
    response = client.post(
        f"/api/fiscal/documents/{document['id']}/{name}",
        json={"version": document["version"], "reason": reason},
        headers=auth[1],
    )
    assert response.status_code == expected, response.text
    return response.json()


def test_fake_provider_is_identified_and_deterministic():
    provider = FakeFiscalProvider()
    request = EmissionRequest("key-1", {}, "9193", START, START, 1000, "Locação")
    first, again = provider.emit(request), provider.emit(request)
    assert first.status == "EMITIDO" and first.series == "SIM" and first.access_key is None
    assert (first.provider_ref, first.number) == (again.provider_ref, again.number)
    assert first.raw["simulacao"] is True
    assert (
        provider.environment == "SIMULACAO" and provider.get_pdf(first.provider_ref)[:4] == b"%PDF"
    )
    assert NOTICE.encode() in provider.get_xml(first.provider_ref)
    assert build_provider(Settings(_env_file=None)).name == "fake"
    with pytest.raises(HTTPException) as error:
        build_provider(Settings(_env_file=None, fiscal_provider="nuvem_fiscal"))
    assert error.value.status_code == 409


def test_emission_lifecycle_files_and_trail(client, admin, base):
    person, item = base
    contract = confirmed(client, admin, person, [line(item["id"])])
    info = client.get("/api/fiscal/provider").json()
    assert info == {
        "name": "fake",
        "environment": "SIMULACAO",
        "is_simulation": True,
        "document_kind": "",
    }
    payload = fiscal_body(person["id"], contract["id"])
    document = post(client, admin, "fiscal/documents", payload)
    assert document["status"] == "PENDENTE" and document["amount"] == "2340.00"
    assert document["is_simulation"] is True and document["has_pdf"] is False
    # Reenvio da mesma criação devolve o mesmo documento.
    assert post(client, admin, "fiscal/documents", payload)["id"] == document["id"]
    assert client.get(f"/api/fiscal/documents/{document['id']}/pdf").status_code == 404

    issued = action(client, admin, document, "emit")
    assert issued["status"] == "EMITIDO" and issued["series"] == "SIM" and issued["number"]
    assert issued["has_pdf"] and issued["has_xml"]
    assert [e["action"] for e in issued["events"]] == ["CREATE", "EMIT"]
    assert issued["events"][1]["response"]["simulacao"] is True
    action(client, admin, issued, "emit", expected=409)  # não emite duas vezes
    pdf = client.get(f"/api/fiscal/documents/{document['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    xml = client.get(f"/api/fiscal/documents/{document['id']}/xml")
    assert xml.status_code == 200 and "SIMULAÇÃO" in xml.text
    action(client, admin, issued, "cancel", "abc", expected=422)
    cancelled = action(client, admin, issued, "cancel", "Emitido com valor incorreto")
    assert cancelled["status"] == "CANCELADO"
    assert cancelled["cancel_reason"] == "Emitido com valor incorreto"
    action(client, admin, cancelled, "emit", expected=409)
    listing = client.get("/api/fiscal/documents", params={"contract_id": contract["id"]}).json()
    assert listing["total"] == 1 and listing["items"][0]["status"] == "CANCELADO"
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(FiscalDocument)) == 1
        assert db.scalar(select(func.count()).select_from(FiscalEvent)) == 3


def test_error_retry_and_processing_states(client, admin, base):
    person, _item = base
    failing = post(
        client, admin, "fiscal/documents", fiscal_body(person["id"], description="Locação [ERRO]")
    )
    failed = action(client, admin, failing, "emit")
    assert failed["status"] == "ERRO" and "Rejeição simulada" in failed["error_message"]
    assert failed["has_pdf"] is False and failed["number"] is None
    retried = action(client, admin, failed, "emit")  # mesma chave: nova tentativa, mesmo documento
    assert retried["status"] == "ERRO" and retried["provider_ref"] == failed["provider_ref"]
    assert action(client, admin, retried, "cancel", "Dados incorretos")["status"] == "CANCELADO"

    slow = post(
        client,
        admin,
        "fiscal/documents",
        fiscal_body(person["id"], description="Locação [PROCESSANDO]"),
    )
    action(client, admin, slow, "refresh", expected=409)
    processing = action(client, admin, slow, "emit")
    assert processing["status"] == "PROCESSANDO"
    action(client, admin, processing, "cancel", "Tentativa indevida", expected=409)
    action(client, admin, slow, "refresh", expected=409)  # versão antiga
    done = action(client, admin, processing, "refresh")
    assert done["status"] == "EMITIDO" and done["has_pdf"]


def test_validation_and_contract_ownership(client, admin, base):
    person, item = base
    other = customer(client, admin, "11144477735")
    contract = confirmed(client, admin, person, [line(item["id"])])
    draft = post(
        client,
        admin,
        "contracts",
        {"customer_id": person["id"], "start_date": START, "items": [line(item["id"])]},
    )

    def create(payload, expected):
        response = client.post("/api/fiscal/documents", json=payload, headers=admin[1])
        assert response.status_code == expected, response.text

    create(fiscal_body(other["id"], contract["id"]), 409)  # contrato de outro cliente
    create(fiscal_body(person["id"], draft["id"]), 409)  # rascunho
    create(fiscal_body(9999), 404)
    create(fiscal_body(person["id"], amount="0.00"), 422)
    create(fiscal_body(person["id"], amount=10.5), 422)  # float nunca é aceito
    create(fiscal_body(person["id"], period_end="2020-01-01"), 422)
    create(fiscal_body(person["id"], description="abc"), 422)
    create(fiscal_body(person["id"]), 201)  # sem contrato é permitido


@pytest.mark.parametrize(
    "role,can_read,can_write",
    [("FINANCEIRO", True, True), ("COMERCIAL", False, False), ("CLIENTE", False, False)],
)
def test_fiscal_roles(client, admin, base, role, can_read, can_write):
    person, _item = base
    document = post(client, admin, "fiscal/documents", fiscal_body(person["id"]))
    worker = login(client, "worker", role)
    assert client.get("/api/fiscal/documents").status_code == (200 if can_read else 403)
    assert client.get("/api/fiscal/provider").status_code == (200 if can_read else 403)
    created = client.post(
        "/api/fiscal/documents", json=fiscal_body(person["id"]), headers=worker[1]
    )
    assert created.status_code == (201 if can_write else 403)
    emit = client.post(
        f"/api/fiscal/documents/{document['id']}/emit",
        json={"version": document["version"]},
        headers=worker[1],
    )
    assert emit.status_code == (200 if can_write else 403)
    client.cookies.clear()
    assert client.get(f"/api/fiscal/documents/{document['id']}/pdf").status_code == 401
