from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.models import AuditLog, User
from app.auth.service import IdentityService
from app.masters.models import Customer, Price, Product
from app.masters.schemas import MovementInput
from app.masters.service import MasterService
from app.persistence.database import build_engine

HEADERS = {"Origin": "http://localhost:5173", "X-LocaControl-Request": "1"}
PASSWORD = "Master-test-fixture-only!"


@pytest.fixture
def admin(client):
    with Session(client.app.state.engine) as db:
        user = IdentityService(db, local=True).create_user(
            "admin", "Admin", PASSWORD, ["ADMINISTRADOR"], must_change=False
        )
        db.commit()
        user_id = user.id
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    )
    assert response.status_code == 200
    return user_id, {**HEADERS, "X-CSRF-Token": response.json()["csrf_token"]}


def create(client, admin, path, body):
    response = client.post("/api/" + path, json=body, headers=admin[1])
    assert response.status_code == 201, response.text
    return response.json()


def product(client, admin, individual=False, code="P-001"):
    return create(
        client,
        admin,
        "products",
        {
            "code": code,
            "name": "Produto de teste",
            "unit": "UN",
            "individual_tracking": individual,
        },
    )


def movement(product_id, quantity="1.000", source=None, target="DISPONIVEL"):
    return {
        "product_id": product_id,
        "quantity": quantity,
        "from_status": source,
        "to_status": target,
        "reason": "Ajuste de inventário",
        "request_key": str(uuid4()),
    }


def test_customer_crud_addresses_duplicate_version_and_audit(client, admin):
    body = {
        "person_type": "PF",
        "legal_name": "Maria Teste",
        "document": "529.982.247-25",
        "email": "MARIA@EXAMPLE.COM",
        "addresses": [
            {
                "street": "Rua Um, 20",
                "city": "São Paulo",
                "state": "SP",
                "postal_code": "01001-000",
            },
            {
                "label": "Obra",
                "street": "Rua Dois",
                "city": "São Paulo",
                "state": "SP",
                "postal_code": "01001001",
            },
        ],
    }
    row = create(client, admin, "customers", body)
    assert row["document"] == "52998224725" and row["email"] == "maria@example.com"
    assert len(row["addresses"]) == 2
    assert client.post("/api/customers", json=body, headers=admin[1]).status_code == 409
    updated = {**body, "version": row["version"], "legal_name": "Maria Atualizada"}
    response = client.put(f"/api/customers/{row['id']}", json=updated, headers=admin[1])
    assert response.status_code == 200 and response.json()["version"] == 2
    assert (
        client.put(f"/api/customers/{row['id']}", json=updated, headers=admin[1]).status_code == 409
    )
    assert client.get("/api/customers?q=Atualizada").json()["total"] == 1
    assert client.get("/api/customers?q=%25").json()["total"] == 0
    response = client.delete(f"/api/customers/{row['id']}?version=2", headers=admin[1])
    assert response.status_code == 200 and not response.json()["is_active"]
    assert client.get("/api/customers?active=false").json()["total"] == 1
    assert client.get(f"/api/customers/{row['id']}").status_code == 200
    with Session(client.app.state.engine) as db:
        events = list(db.scalars(select(AuditLog).where(AuditLog.entity == "customers")))
        assert len(events) == 3 and all(e.actor_id == admin[0] for e in events)
        assert events[1].changes["before"]["legal_name"] == "Maria Teste"


def test_product_conflicts_and_control_change_after_history(client, admin):
    row = product(client, admin)
    assert (
        client.post(
            "/api/products", json={"code": "p-001", "name": "Outro", "unit": "UN"}, headers=admin[1]
        ).status_code
        == 409
    )
    create(client, admin, "stock/movements", movement(row["id"]))
    body = {
        k: row[k]
        for k in (
            "code",
            "name",
            "description",
            "category",
            "unit",
            "individual_tracking",
            "is_active",
            "version",
        )
    }
    body["individual_tracking"] = True
    assert client.put(f"/api/products/{row['id']}", json=body, headers=admin[1]).status_code == 409
    assert (
        client.delete(f"/api/products/{row['id']}?version=1", headers=admin[1]).status_code == 200
    )


def test_stock_exact_balance_idempotency_and_no_negative(client, admin):
    row = product(client, admin)
    entry = movement(row["id"], "1.125")
    original = create(client, admin, "stock/movements", entry)
    repeat = create(client, admin, "stock/movements", entry)
    assert repeat["id"] == original["id"]
    create(
        client, admin, "stock/movements", movement(row["id"], "0.125", "DISPONIVEL", "MANUTENCAO")
    )
    balances = client.get("/api/stock").json()["items"][0]["balances"]
    assert balances["DISPONIVEL"] == "1.000" and balances["MANUTENCAO"] == "0.125"
    response = client.post(
        "/api/stock/movements",
        json=movement(row["id"], "1.001", "DISPONIVEL", "LOCADO"),
        headers=admin[1],
    )
    assert response.status_code == 409
    conflict = {**entry, "quantity": "2.000"}
    assert client.post("/api/stock/movements", json=conflict, headers=admin[1]).status_code == 409
    assert client.get("/api/stock/movements").json()["total"] == 2


@pytest.mark.parametrize("quantity", [1.1, "0", "-1", "0.0001", "NaN", "1000000000"])
def test_invalid_quantities_rejected(client, admin, quantity):
    row = product(client, admin)
    body = movement(row["id"])
    body["quantity"] = quantity
    assert client.post("/api/stock/movements", json=body, headers=admin[1]).status_code == 422
    assert client.get("/api/stock/movements").json()["total"] == 0


def test_equipment_link_unique_status_history_and_retirement(client, admin):
    bulk = product(client, admin)
    body = {"product_id": bulk["id"], "code": "EQ-1", "asset_tag": "PAT-1", "serial_number": "SN-1"}
    assert client.post("/api/equipment", json=body, headers=admin[1]).status_code == 409
    unit_product = product(client, admin, True, "P-UNIT")
    body["product_id"] = unit_product["id"]
    row = create(client, admin, "equipment", body)
    assert client.get("/api/stock?q=P-UNIT").json()["items"][0]["balances"]["DISPONIVEL"] == "1.000"
    assert (
        client.post("/api/equipment", json={**body, "code": "EQ-2"}, headers=admin[1]).status_code
        == 409
    )
    response = client.post(
        f"/api/equipment/{row['id']}/status",
        json={"version": 1, "status": "LOCADO", "reason": "Locação manual teste"},
        headers=admin[1],
    )
    assert response.status_code == 200
    assert (
        client.delete(
            f"/api/equipment/{row['id']}?version=2&reason=Baixa%20teste", headers=admin[1]
        ).status_code
        == 409
    )
    assert (
        client.delete(
            f"/api/equipment/{row['id']}?version=0&reason=x", headers=admin[1]
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/equipment/{row['id']}/status",
            json={"version": 2, "status": "DISPONIVEL", "reason": "Retorno de teste"},
            headers=admin[1],
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/equipment/{row['id']}?version=3&reason=Baixa%20teste", headers=admin[1]
        ).status_code
        == 200
    )
    assert client.get("/api/stock?q=P-UNIT").json()["items"][0]["balances"]["BAIXADO"] == "1.000"
    assert (
        client.post(
            f"/api/equipment/{row['id']}/status",
            json={"version": 4, "status": "DISPONIVEL", "reason": "Retorno inválido"},
            headers=admin[1],
        ).status_code
        == 409
    )
    assert client.get(f"/api/stock/movements?product_id={unit_product['id']}").json()["total"] == 4


@pytest.mark.parametrize("period", ["DIARIA", "SEMANAL", "QUINZENAL", "MENSAL"])
def test_price_versions_exact_effective_and_retire(client, admin, period):
    row = product(client, admin)
    body = {
        "product_id": row["id"],
        "period": period,
        "effective_date": "2026-10-01",
        "amount": "0.10",
        "reason": "Tabela inicial",
    }
    first = create(client, admin, "prices", body)
    assert first["amount"] == "0.10"
    second = create(
        client, admin, "prices", {**body, "effective_date": "2026-11-01", "amount": "19.99"}
    )
    base = f"/api/prices/effective?product_id={row['id']}&period={period}&at="
    assert client.get(base + "2026-09-30").status_code == 404
    assert client.get(base + "2026-10-15").json()["id"] == first["id"]
    assert client.get(base + "2026-11-01").json()["id"] == second["id"]
    revised = client.put(
        f"/api/prices/{second['id']}",
        json={**body, "effective_date": "2026-11-01", "amount": "20.01"},
        headers=admin[1],
    )
    assert revised.status_code == 201 and revised.json()["supersedes_id"] == second["id"]
    assert client.get(f"/api/prices/{second['id']}").json()["amount"] == "19.99"
    assert client.delete(f"/api/prices/{second['id']}", headers=admin[1]).status_code in (409, 422)
    retire = client.request(
        "DELETE",
        f"/api/prices/{revised.json()['id']}",
        json={"reason": "Tabela suspensa"},
        headers=admin[1],
    )
    assert retire.status_code == 201 and retire.json()["amount"] is None
    assert client.get(base + "2026-11-15").status_code == 404
    assert client.get(base + "2026-10-15").json()["amount"] == "0.10"
    with Session(client.app.state.engine) as db:
        assert db.get(Price, first["id"]).amount_cents == 10
        assert db.scalar(select(func.count()).select_from(Price)) == 4


@pytest.mark.parametrize(
    "role,can_read,can_write",
    [
        ("COMERCIAL", True, True),
        ("OPERACAO", False, False),
        ("FINANCEIRO", True, False),
        ("CLIENTE", False, False),
    ],
)
def test_roles_and_csrf_direct_api(client, role, can_read, can_write):
    with Session(client.app.state.engine) as db:
        IdentityService(db, local=True).create_user(
            "worker", "Worker", PASSWORD, [role], must_change=False
        )
        db.commit()
    response = client.post(
        "/api/auth/login", json={"username": "worker", "password": PASSWORD}, headers=HEADERS
    )
    headers = {**HEADERS, "X-CSRF-Token": response.json()["csrf_token"]}
    assert client.get("/api/customers").status_code == (200 if can_read else 403)
    body = {"person_type": "PF", "legal_name": "Cliente teste", "document": "52998224725"}
    assert client.post("/api/customers", json=body, headers=HEADERS).status_code == 403
    assert client.post("/api/customers", json=body, headers=headers).status_code == (
        201 if can_write else 403
    )


def test_audit_failure_rolls_back_business_write(client, admin, monkeypatch):
    def fail(*_args, **_kwargs):
        raise SQLAlchemyError("fixture audit failure")

    monkeypatch.setattr(IdentityService, "audit", fail)
    response = client.post(
        "/api/products", json={"code": "ROLLBACK", "name": "Teste", "unit": "UN"}, headers=admin[1]
    )
    assert response.status_code == 503
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Product)) == 0


def test_concurrent_stock_withdrawals_preserve_balance(client, admin):
    row = product(client, admin)
    create(client, admin, "stock/movements", movement(row["id"], "1.000"))
    barrier = Barrier(2)

    def withdraw(_index):
        payload = MovementInput(**movement(row["id"], "1.000", "DISPONIVEL", "LOCADO"))
        barrier.wait()
        with Session(client.app.state.engine) as db:
            db.execute(text("BEGIN IMMEDIATE"))
            try:
                actor = db.get(User, admin[0])
                MasterService(db, actor).move(payload)
                db.commit()
                return 201
            except HTTPException as error:
                db.rollback()
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(withdraw, [1, 2])) == [201, 409]
    balances = client.get("/api/stock").json()["items"][0]["balances"]
    assert balances["DISPONIVEL"] == "0.000" and balances["LOCADO"] == "1.000"


def test_upgrade_0002_preserves_existing_account(migration_config):
    command.upgrade(migration_config, "0002_identity")
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
            assert user.password_hash == original_hash and user.username == "existing"
            assert len(user.roles[0].permissions) == 30
            assert db.scalar(select(func.count()).select_from(Customer)) == 0
        command.downgrade(migration_config, "0002_identity")
        with Session(engine) as db:
            assert db.get(User, user_id).password_hash == original_hash
    finally:
        engine.dispose()
