from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.models import AuditLog, User
from app.auth.service import IdentityService
from app.core.clock import business_today
from app.persistence.database import build_engine
from app.quotes import calc
from app.quotes.models import Quote, QuoteItem
from app.quotes.schemas import QuoteInput
from app.quotes.service import QuoteService

HEADERS = {"Origin": "http://localhost:5173", "X-LocaControl-Request": "1"}
PASSWORD = "Quote-test-fixture-only!"
TODAY = business_today()
START = TODAY.isoformat()
VALID = (TODAY + timedelta(days=10)).isoformat()


def login(client, username, role):
    with Session(client.app.state.engine) as db:
        user = IdentityService(db, local=True).create_user(
            username, username.title(), PASSWORD, [role], must_change=False
        )
        db.commit()
        user_id = user.id
    client.cookies.clear()
    response = client.post(
        "/api/auth/login", json={"username": username, "password": PASSWORD}, headers=HEADERS
    )
    assert response.status_code == 200
    headers = {**HEADERS, "X-CSRF-Token": response.json()["csrf_token"]}
    return user_id, headers, list(client.cookies.jar)


def switch(client, auth):
    """One TestClient holds a single cookie jar; select whose session the next calls use."""
    client.cookies.clear()
    for cookie in auth[2]:
        client.cookies.jar.set_cookie(cookie)


@pytest.fixture
def admin(client):
    return login(client, "admin", "ADMINISTRADOR")


def post(client, auth, path, body, expected=201):
    switch(client, auth)
    response = client.post("/api/" + path, json=body, headers=auth[1])
    assert response.status_code == expected, response.text
    return response.json()


def customer(client, admin, document="52998224725"):
    return post(
        client,
        admin,
        "customers",
        {
            "person_type": "PF",
            "legal_name": "Maria Locatária",
            "document": document,
            "addresses": [
                {
                    "street": "Rua Um, 20",
                    "city": "São Paulo",
                    "state": "SP",
                    "postal_code": "01001000",
                }
            ],
        },
    )


def product(client, admin, code="BET-400", individual=False, prices=None):
    row = post(
        client,
        admin,
        "products",
        {"code": code, "name": f"Produto {code}", "unit": "UN", "individual_tracking": individual},
    )
    for period, amount in (prices or {"DIARIA": "90.00", "SEMANAL": "390.00"}).items():
        post(
            client,
            admin,
            "prices",
            {
                "product_id": row["id"],
                "period": period,
                "effective_date": "2026-01-01",
                "amount": amount,
                "reason": "Tabela inicial",
            },
        )
    return row


def body(customer_id, items, **extra):
    return {
        "customer_id": customer_id,
        "start_date": START,
        "valid_until": VALID,
        "items": items,
        **extra,
    }


def line(product_id, quantity="2.000", period="SEMANAL", count=3, unit_price=None):
    return {
        "product_id": product_id,
        "quantity": quantity,
        "period": period,
        "period_count": count,
        "unit_price": unit_price,
    }


@pytest.fixture
def base(client, admin):
    return customer(client, admin), product(client, admin)


@pytest.mark.parametrize(
    "quantity_milli,price_cents,periods,expected",
    [
        (2000, 39000, 3, 234000),
        (1500, 33, 1, 50),  # 49.5 centavos arredonda para cima
        (333, 1, 1, 0),  # 0.333 centavo arredonda para baixo
        (1, 99999999999, 1, 100000000),
        (2500, 1999, 7, 34983),  # 34982.5 -> meio para cima
    ],
)
def test_item_total_is_exact_and_rounds_half_up(quantity_milli, price_cents, periods, expected):
    result = calc.item_total_cents(quantity_milli, price_cents, periods)
    assert result == expected and isinstance(result, int)


def test_end_date_uses_running_days_per_period():
    start = date(2026, 3, 10)
    assert calc.end_date(start, "DIARIA", 1) == date(2026, 3, 11)
    assert calc.end_date(start, "SEMANAL", 3) == date(2026, 3, 31)
    assert calc.end_date(start, "QUINZENAL", 1) == date(2026, 3, 25)
    assert calc.end_date(start, "MENSAL", 2) == date(2026, 5, 9)


def test_create_numbers_totals_snapshots_and_audit(client, admin, base):
    person, item = base
    other = product(client, admin, "AND-1", prices={"MENSAL": "12.35"})
    quote = post(
        client,
        admin,
        "quotes",
        body(person["id"], [line(item["id"]), line(other["id"], "10.500", "MENSAL", 2)]),
    )
    assert quote["number"] == f"ORC-{TODAY.year}-000001" and quote["status"] == "RASCUNHO"
    first, second = quote["items"]
    assert (first["table_price"], first["unit_price"], first["total"]) == (
        "390.00",
        "390.00",
        "2340.00",
    )
    assert first["end_date"] == (TODAY + timedelta(days=21)).isoformat()
    assert second["total"] == "259.35" and second["quantity"] == "10.500"
    assert quote["total"] == "2599.35" and quote["negotiated_difference"] == "0.00"
    assert quote["customer"]["legal_name"] == "Maria Locatária"
    assert quote["customer"]["address"]["city"] == "São Paulo"
    assert quote["transitions"][0]["to_status"] == "RASCUNHO"
    again = post(client, admin, "quotes", body(person["id"], [line(item["id"])]))
    assert again["number"] == f"ORC-{TODAY.year}-000002"
    listing = client.get("/api/quotes", params={"q": "maria"}).json()
    assert listing["total"] == 2 and listing["items"][0]["item_count"] == 1
    assert client.get("/api/quotes", params={"q": quote["number"]}).json()["total"] == 1
    with Session(client.app.state.engine) as db:
        assert (
            db.scalar(
                select(func.count()).select_from(AuditLog).where(AuditLog.action == "quote.created")
            )
            == 2
        )


def test_table_changes_never_rewrite_a_saved_quote(client, admin, base):
    person, item = base
    quote = post(client, admin, "quotes", body(person["id"], [line(item["id"])]))
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
    assert client.get(f"/api/quotes/{quote['id']}").json()["total"] == "2340.00"
    edit = body(person["id"], [line(item["id"])], notes="Entrega na obra", version=quote["version"])
    kept = client.put(f"/api/quotes/{quote['id']}", json=edit, headers=admin[1])
    assert kept.status_code == 200 and kept.json()["total"] == "2340.00"
    assert kept.json()["items"][0]["table_price"] == "390.00"
    refresh = {**edit, "version": kept.json()["version"], "refresh_prices": True}
    refreshed = client.put(f"/api/quotes/{quote['id']}", json=refresh, headers=admin[1])
    assert refreshed.json()["items"][0]["table_price"] == "500.00"
    assert refreshed.json()["total"] == "3000.00"
    stale = client.put(f"/api/quotes/{quote['id']}", json=edit, headers=admin[1])
    assert stale.status_code == 409


def test_negotiated_price_requires_permission_and_keeps_both_values(client, admin, base):
    person, item = base
    seller = login(client, "vendedor", "COMERCIAL")
    negotiated = body(person["id"], [line(item["id"], unit_price="350.00")])
    assert client.post("/api/quotes", json=negotiated, headers=seller[1]).status_code == 403
    quote = post(client, admin, "quotes", negotiated)
    row = quote["items"][0]
    assert (row["table_price"], row["unit_price"], row["negotiated"]) == ("390.00", "350.00", True)
    assert quote["total"] == "2100.00" and quote["table_total"] == "2340.00"
    assert quote["negotiated_difference"] == "240.00"
    # Sem a permissão, o vendedor mantém o preço já negociado, mas não o altera.
    keep = {**negotiated, "notes": "Revisado", "version": quote["version"]}
    switch(client, seller)
    kept = client.put(f"/api/quotes/{quote['id']}", json=keep, headers=seller[1])
    assert kept.status_code == 200 and kept.json()["total"] == "2100.00"
    change = body(
        person["id"], [line(item["id"], unit_price="300.00")], version=kept.json()["version"]
    )
    assert (
        client.put(f"/api/quotes/{quote['id']}", json=change, headers=seller[1]).status_code == 403
    )


def test_transitions_reasons_and_edit_lock(client, admin, base):
    person, item = base
    quote = post(client, admin, "quotes", body(person["id"], [line(item["id"])]))
    url = f"/api/quotes/{quote['id']}"

    def act(action, version, reason="", expected=200):
        response = client.post(
            f"{url}/{action}", json={"version": version, "reason": reason}, headers=admin[1]
        )
        assert response.status_code == expected, response.text
        return response.json()

    act("reject", quote["version"], "Cliente desistiu", expected=409)
    sent = act("send", quote["version"])
    assert sent["status"] == "ENVIADO"
    act("send", quote["version"], expected=409)  # versão antiga
    edit = body(person["id"], [line(item["id"])], version=sent["version"])
    assert client.put(url, json=edit, headers=admin[1]).status_code == 409
    act("reject", sent["version"], "abc", expected=422)
    draft = act("reopen", sent["version"])
    assert draft["status"] == "RASCUNHO"
    approved = act("approve", draft["version"])
    assert approved["status"] == "APROVADO"
    act("reopen", approved["version"], expected=409)
    cancelled = act("cancel", approved["version"], "Equipamento vendido")
    assert cancelled["status"] == "CANCELADO"
    assert cancelled["status_reason"] == "Equipamento vendido"
    assert [t["to_status"] for t in cancelled["transitions"]] == [
        "RASCUNHO",
        "ENVIADO",
        "RASCUNHO",
        "APROVADO",
        "CANCELADO",
    ]
    act("approve", cancelled["version"], expected=409)


def test_expired_is_derived_and_blocks_approval(client, admin, base):
    person, item = base
    quote = post(client, admin, "quotes", body(person["id"], [line(item["id"])]))
    url = f"/api/quotes/{quote['id']}"
    sent = client.post(f"{url}/send", json={"version": quote["version"]}, headers=admin[1]).json()
    with Session(client.app.state.engine) as db:
        db.get(Quote, quote["id"]).valid_until = (TODAY - timedelta(days=1)).isoformat()
        db.commit()
    assert client.get(url).json()["status"] == "EXPIRADO"
    assert client.get("/api/quotes", params={"status": "EXPIRADO"}).json()["total"] == 1
    assert client.get("/api/quotes", params={"status": "ENVIADO"}).json()["total"] == 0
    version = {"version": sent["version"], "reason": "Cliente recusou"}
    assert client.post(f"{url}/approve", json=version, headers=admin[1]).status_code == 409
    assert client.post(f"{url}/reject", json=version, headers=admin[1]).status_code == 409
    reopened = client.post(f"{url}/reopen", json=version, headers=admin[1])
    assert reopened.status_code == 200 and reopened.json()["status"] == "RASCUNHO"
    past = body(person["id"], [line(item["id"])], version=reopened.json()["version"])
    past["valid_until"] = (TODAY - timedelta(days=1)).isoformat()
    assert client.put(url, json=past, headers=admin[1]).status_code == 422


def test_duplicate_reprices_and_reports_lines_not_copied(client, admin, base):
    person, item = base
    gone = product(client, admin, "OLD-1")
    quote = post(
        client,
        admin,
        "quotes",
        body(person["id"], [line(item["id"], unit_price="350.00"), line(gone["id"])]),
    )
    retired = client.delete(
        f"/api/products/{gone['id']}", params={"version": gone["version"]}, headers=admin[1]
    )
    assert retired.status_code == 200
    copy = post(client, admin, f"quotes/{quote['id']}/duplicate", {})
    assert copy["number"].endswith("000002") and copy["status"] == "RASCUNHO"
    assert copy["duplicated_from_id"] == quote["id"]
    assert len(copy["items"]) == 1 and copy["items"][0]["unit_price"] == "350.00"
    assert len(copy["warnings"]) == 1 and "OLD-1" in copy["warnings"][0]
    assert client.get(f"/api/quotes/{quote['id']}").json()["status"] == "RASCUNHO"
    assert len(client.get(f"/api/quotes/{quote['id']}").json()["items"]) == 2


def test_validation_of_lines_prices_and_customer(client, admin, base):
    person, item = base
    unit = product(client, admin, "GER-1", individual=True)
    fractional = body(person["id"], [line(unit["id"], "1.500")])
    assert client.post("/api/quotes", json=fractional, headers=admin[1]).status_code == 422
    no_price = body(person["id"], [line(item["id"], period="MENSAL")])
    response = client.post("/api/quotes", json=no_price, headers=admin[1])
    assert response.status_code == 409 and "mensal" in response.json()["detail"]
    repeated = body(person["id"], [line(item["id"]), line(item["id"])])
    assert client.post("/api/quotes", json=repeated, headers=admin[1]).status_code == 422
    for bad in ("0", "1.2345", 2, "-1"):
        payload = body(person["id"], [line(item["id"], bad)])
        assert client.post("/api/quotes", json=payload, headers=admin[1]).status_code == 422
    assert (
        client.post("/api/quotes", json=body(999, [line(item["id"])]), headers=admin[1]).status_code
        == 404
    )
    off = client.delete(
        f"/api/customers/{person['id']}", params={"version": person["version"]}, headers=admin[1]
    )
    assert off.status_code == 200
    blocked = client.post(
        "/api/quotes", json=body(person["id"], [line(item["id"])]), headers=admin[1]
    )
    assert blocked.status_code == 409
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Quote)) == 0
        assert db.scalar(select(func.count()).select_from(QuoteItem)) == 0


def test_pricing_shows_stock_without_reserving(client, admin, base):
    _person, item = base
    post(
        client,
        admin,
        "stock/movements",
        {
            "product_id": item["id"],
            "quantity": "5.000",
            "from_status": None,
            "to_status": "DISPONIVEL",
            "reason": "Entrada inicial",
            "request_key": "5b1f0c1e-6a53-4f0e-9d53-6f2f0a8f6f01",
        },
    )
    params = {"product_id": item["id"], "period": "SEMANAL", "at": START}
    info = client.get("/api/quotes/pricing", params=params).json()
    assert info["table_price"] == "390.00" and info["available"] == "5.000"
    assert info["period_days"] == 7
    missing = client.get("/api/quotes/pricing", params={**params, "period": "MENSAL"}).json()
    assert missing["table_price"] is None
    person = customer(client, admin, "11144477735")
    post(client, admin, "quotes", body(person["id"], [line(item["id"], "9.000")]))
    balances = client.get("/api/stock").json()["items"][0]["balances"]
    assert balances["DISPONIVEL"] == "5.000" and balances["RESERVADO"] == "0.000"


def test_pdf_uses_snapshot_and_requires_session(client, admin, base):
    person, item = base
    quote = post(
        client,
        admin,
        "quotes",
        body(
            person["id"],
            [line(item["id"], unit_price="350.00")],
            notes="Frete por conta do cliente",
        ),
    )
    response = client.get(f"/api/quotes/{quote['id']}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert quote["number"] in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF") and len(response.content) > 1500
    assert client.get("/api/quotes/9999/pdf").status_code == 404
    client.cookies.clear()
    assert client.get(f"/api/quotes/{quote['id']}/pdf").status_code == 401
    assert client.get("/api/quotes").status_code == 401


@pytest.mark.parametrize(
    "role,can_read,can_write,can_approve",
    [
        ("COMERCIAL", True, True, True),
        ("FINANCEIRO", True, False, False),
        ("OPERACAO", False, False, False),
        ("CLIENTE", False, False, False),
    ],
)
def test_roles_are_enforced_by_the_api(client, admin, base, role, can_read, can_write, can_approve):
    person, item = base
    quote = post(client, admin, "quotes", body(person["id"], [line(item["id"])]))
    worker = login(client, "worker", role)
    assert client.get("/api/quotes").status_code == (200 if can_read else 403)
    assert client.get(f"/api/quotes/{quote['id']}").status_code == (200 if can_read else 403)
    payload = body(person["id"], [line(item["id"])])
    assert client.post("/api/quotes", json=payload, headers=HEADERS).status_code == 403  # sem CSRF
    created = client.post("/api/quotes", json=payload, headers=worker[1])
    assert created.status_code == (201 if can_write else 403)
    approve = client.post(
        f"/api/quotes/{quote['id']}/approve", json={"version": quote["version"]}, headers=worker[1]
    )
    assert approve.status_code == (200 if can_approve else 403)


def test_audit_failure_rolls_back_quote(client, admin, base, monkeypatch):
    person, item = base

    def fail(*_args, **_kwargs):
        raise SQLAlchemyError("fixture audit failure")

    monkeypatch.setattr(IdentityService, "audit", fail)
    response = client.post(
        "/api/quotes", json=body(person["id"], [line(item["id"])]), headers=admin[1]
    )
    assert response.status_code == 503
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Quote)) == 0


def test_concurrent_creation_never_reuses_a_number(client, admin, base):
    person, item = base
    barrier = Barrier(4)

    def create(_index):
        payload = QuoteInput(**body(person["id"], [line(item["id"])]))
        barrier.wait()
        with Session(client.app.state.engine) as db:
            db.execute(text("BEGIN IMMEDIATE"))
            result = QuoteService(db, db.get(User, admin[0])).save(payload)
            db.commit()
            return result["number"]

    with ThreadPoolExecutor(max_workers=4) as executor:
        numbers = list(executor.map(create, range(4)))
    assert sorted(numbers) == [f"ORC-{TODAY.year}-{n:06d}" for n in range(1, 5)]


def test_upgrade_0004_to_head_preserves_account_and_grants(migration_config):
    command.upgrade(migration_config, "0004_imports")
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
            user = db.get(User, user_id)
            assert user.password_hash == original_hash
            codes = {p.code for p in user.roles[0].permissions}
            assert {"quotes.read", "quotes.write", "quotes.approve", "quotes.negotiate"} <= codes
            grants = dict(
                db.execute(
                    text(
                        "SELECT r.code, COUNT(*) FROM roles r "
                        "JOIN role_permissions rp ON rp.role_id = r.id "
                        "JOIN permissions p ON p.id = rp.permission_id "
                        "WHERE p.code LIKE 'quotes.%' GROUP BY r.code"
                    )
                ).all()
            )
            assert grants == {"ADMINISTRADOR": 4, "COMERCIAL": 3, "FINANCEIRO": 1}
        command.downgrade(migration_config, "0004_imports")
        with Session(engine) as db:
            assert db.get(User, user_id).password_hash == original_hash
            assert db.scalar(text("SELECT COUNT(*) FROM permissions")) == 18
    finally:
        engine.dispose()
