import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.cli import run_local
from app.auth.models import AuditLog, AuthSession, User
from app.auth.security import COOKIE, digest, verify_password
from app.auth.service import IdentityService

PASSWORD = "Fixture-only-secure-2026!"
NEW_PASSWORD = "Another-fixture-secure-2026!"
HEADERS = {"Origin": "http://localhost:5173", "X-LocaControl-Request": "1"}


def seed(client, name="admin", role="ADMINISTRADOR", must_change=False):
    with Session(client.app.state.engine) as db:
        db.execute(text("BEGIN IMMEDIATE"))
        user = IdentityService(db, local=True).create_user(
            name, name.title(), PASSWORD, [role], must_change=must_change
        )
        user_id = user.id
        db.commit()
    return user_id


def login(client, name="admin", password=PASSWORD):
    response = client.post(
        "/api/auth/login", json={"username": name, "password": password}, headers=HEADERS
    )
    assert response.status_code == 200, response.text
    return {**HEADERS, "X-CSRF-Token": response.json()["csrf_token"]}


def test_bootstrap_once_and_local_recovery(client):
    settings = client.app.state.settings
    run_local("bootstrap", "admin", "Administrador", PASSWORD, settings)
    with pytest.raises(HTTPException) as error:
        run_local("bootstrap", "other", "Outro admin", PASSWORD, settings)
    assert error.value.status_code == 409
    login(client)
    run_local("recover", "admin", "Operador", NEW_PASSWORD, settings)
    assert client.get("/api/auth/me").status_code == 401
    login(client, password=NEW_PASSWORD)
    assert client.get("/api/auth/me").json()["user"]["must_change_password"]
    with Session(client.app.state.engine) as db:
        actions = list(db.scalars(select(AuditLog.action)))
        assert "bootstrap.completed" in actions and "password.recovered_local" in actions


def test_login_cookie_hash_logout_and_replay(client):
    seed(client)
    response = client.post(
        "/api/auth/login", json={"username": "ADMIN", "password": PASSWORD}, headers=HEADERS
    )
    assert response.status_code == 200
    cookie_header = response.headers["set-cookie"]
    assert (
        "HttpOnly" in cookie_header
        and "SameSite=strict" in cookie_header
        and "Path=/api" in cookie_header
    )
    token = client.cookies.get(COOKIE)
    with Session(client.app.state.engine) as db:
        assert db.get(AuthSession, digest(token)) is not None
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$") and PASSWORD not in user.password_hash
    assert "password" not in response.json()["user"]
    assert "password_hash" not in response.text
    headers = {**HEADERS, "X-CSRF-Token": response.json()["csrf_token"]}
    assert client.get("/api/auth/me").headers["cache-control"] == "no-store"
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    client.cookies.set(COOKIE, token)
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize(
    "path", ["/api/auth/me", "/api/users", "/api/roles", "/api/permissions", "/api/audit-logs"]
)
def test_anonymous_denied(client, path):
    assert client.get(path).status_code == 401


def test_csrf_origin_and_login_csrf(client):
    seed(client)
    body = {"username": "admin", "password": PASSWORD}
    assert client.post("/api/auth/login", json=body).status_code == 403
    assert (
        client.post(
            "/api/auth/login", json=body, headers={**HEADERS, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    headers = login(client)
    for invalid in [
        HEADERS,
        {**headers, "X-CSRF-Token": "wrong"},
        {**headers, "Origin": "https://evil.example"},
    ]:
        assert (
            client.patch("/api/auth/me", json={"name": "Changed"}, headers=invalid).status_code
            == 403
        )
    assert (
        client.patch("/api/auth/me", json={"name": "Changed"}, headers=headers).status_code == 200
    )


def test_login_failure_generic_and_persistent_throttle(client):
    seed(client)
    for name in ["admin", "missing"]:
        body = {"username": name, "password": "wrong"}
        for _ in range(5):
            response = client.post("/api/auth/login", json=body, headers=HEADERS)
            assert response.status_code == 401
            assert response.json()["detail"] == "Usuário ou senha inválidos."
        response = client.post("/api/auth/login", json=body, headers=HEADERS)
        assert response.status_code == 429 and int(response.headers["retry-after"]) > 0


@pytest.mark.parametrize("role", ["COMERCIAL", "OPERACAO", "FINANCEIRO", "CLIENTE"])
def test_default_roles_cannot_access_administration(client, role):
    seed(client, role=role)
    headers = login(client)
    for path in ["/api/users", "/api/roles", "/api/permissions", "/api/audit-logs"]:
        assert client.get(path).status_code == 403
    assert (
        client.post(
            "/api/users",
            json={
                "username": "intruder",
                "name": "Intruder",
                "password": PASSWORD,
                "role_codes": ["ADMINISTRADOR"],
            },
            headers=headers,
        ).status_code
        == 403
    )
    assert client.get("/api/auth/me").status_code == 200


def test_user_management_revocation_and_last_admin(client):
    admin_id = seed(client)
    headers = login(client)
    payload = {
        "username": "worker",
        "name": "Worker",
        "password": PASSWORD,
        "role_codes": ["COMERCIAL"],
    }
    response = client.post("/api/users", json=payload, headers=headers)
    assert response.status_code == 201
    worker_id = response.json()["id"]
    assert client.post("/api/users", json=payload, headers=headers).status_code == 409
    assert (
        client.patch(
            f"/api/users/{admin_id}",
            json={"name": "Admin", "is_active": False, "role_codes": ["ADMINISTRADOR"]},
            headers=headers,
        ).status_code
        == 409
    )
    with TestClient(client.app) as worker:
        worker_headers = login(worker, "worker")
        assert worker.get("/api/auth/me").json()["user"]["must_change_password"]
        assert worker.get("/api/users").status_code == 403
        assert (
            worker.post(
                "/api/auth/password",
                json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
                headers=worker_headers,
            ).status_code
            == 204
        )
        assert worker.get("/api/auth/me").status_code == 401
        login(worker, "worker", NEW_PASSWORD)
        assert (
            client.patch(
                f"/api/users/{worker_id}",
                json={"name": "Worker", "is_active": False, "role_codes": ["COMERCIAL"]},
                headers=headers,
            ).status_code
            == 200
        )
        assert worker.get("/api/auth/me").status_code == 401
    assert client.get("/api/users?q=worker").json()["total"] == 1
    audit = client.get("/api/audit-logs").json()
    assert audit["total"] >= 5 and PASSWORD not in str(audit) and NEW_PASSWORD not in str(audit)
    assert any(
        a["action"] == "user.updated" and a["changes"]["before"]["is_active"]
        for a in audit["items"]
    )


def test_role_update_and_protected_roles(client):
    seed(client)
    seed(client, name="worker", role="COMERCIAL")
    headers = login(client)
    roles = {r["code"]: r for r in client.get("/api/roles").json()}
    for code in ["ADMINISTRADOR", "CLIENTE"]:
        assert (
            client.put(
                f"/api/roles/{roles[code]['id']}/permissions",
                json={"permission_codes": []},
                headers=headers,
            ).status_code
            == 409
        )
    with TestClient(client.app) as worker:
        login(worker, "worker")
        assert (
            client.put(
                f"/api/roles/{roles['COMERCIAL']['id']}/permissions",
                json={"permission_codes": ["workspace.view", "audit.read"]},
                headers=headers,
            ).status_code
            == 200
        )
        assert worker.get("/api/auth/me").status_code == 401
        login(worker, "worker")
        assert worker.get("/api/audit-logs").status_code == 200
    assert (
        client.put(
            f"/api/roles/{roles['COMERCIAL']['id']}/permissions",
            json={"permission_codes": ["invented"]},
            headers=headers,
        ).status_code
        == 422
    )


def test_session_expiry_and_password_validation_no_secret_leak(client):
    seed(client)
    headers = login(client)
    response = client.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "short"},
        headers=headers,
    )
    assert (
        response.status_code == 422
        and "short" not in response.text
        and PASSWORD not in response.text
    )
    assert (
        client.post(
            "/api/auth/password",
            json={"current_password": "wrong", "new_password": NEW_PASSWORD},
            headers=headers,
        ).status_code
        == 400
    )
    with Session(client.app.state.engine) as db:
        auth_session = db.scalar(select(AuthSession))
        auth_session.expires_at = int(time.time()) - 1
        db.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_admin_password_reset_revokes_and_no_mixed_client_roles(client):
    seed(client)
    target = seed(client, name="worker", role="CLIENTE")
    headers = login(client)
    with TestClient(client.app) as worker:
        login(worker, "worker")
        assert (
            client.post(
                f"/api/users/{target}/reset-password",
                json={"new_password": NEW_PASSWORD},
                headers=headers,
            ).status_code
            == 204
        )
        assert worker.get("/api/auth/me").status_code == 401
        login(worker, "worker", NEW_PASSWORD)
        assert worker.get("/api/auth/me").json()["user"]["must_change_password"]
    assert (
        client.patch(
            f"/api/users/{target}",
            json={"name": "Worker", "is_active": True, "role_codes": ["CLIENTE", "ADMINISTRADOR"]},
            headers=headers,
        ).status_code
        == 422
    )


def test_transaction_rolls_back_when_audit_fails(client, monkeypatch):
    seed(client)
    headers = login(client)

    def fail(*_args, **_kwargs):
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(IdentityService, "audit", fail)
    with pytest.raises(RuntimeError):
        client.post(
            "/api/users",
            json={
                "username": "rollback",
                "name": "Rollback",
                "password": PASSWORD,
                "role_codes": ["COMERCIAL"],
            },
            headers=headers,
        )
    with Session(client.app.state.engine) as db:
        assert (
            db.scalar(select(func.count()).select_from(User).where(User.username == "rollback"))
            == 0
        )


def test_secure_cookie_setting_and_salted_hashes(client):
    seed(client)
    seed(client, name="second")
    with Session(client.app.state.engine) as db:
        hashes = list(db.scalars(select(User.password_hash)))
        assert hashes[0] != hashes[1] and all(verify_password(h, PASSWORD) for h in hashes)
    client.app.state.settings.cookie_secure = True
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    )
    assert "Secure" in response.headers["set-cookie"]


def test_default_first_run_account_must_change_password(client):
    from sqlalchemy.orm import Session as OrmSession

    from app.auth.service import IdentityService as Identity

    origin = {"Origin": "http://localhost:5173", "X-LocaControl-Request": "1"}
    with OrmSession(client.app.state.engine) as db:
        assert Identity(db, local=True).bootstrap_default() is not None
        assert Identity(db, local=True).bootstrap_default() is None  # nunca recria
        db.commit()
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin"}, headers=origin
    )
    assert login.status_code == 200 and login.json()["user"]["must_change_password"] is True
    headers = {**origin, "X-CSRF-Token": login.json()["csrf_token"]}
    # Enquanto a senha inicial não for trocada, nenhuma função do sistema é liberada.
    assert client.get("/api/users").status_code == 403
    assert client.get("/api/customers").status_code == 403
    weak = {"current_password": "admin", "new_password": "admin"}
    assert client.post("/api/auth/password", json=weak, headers=headers).status_code == 422
    strong = {"current_password": "admin", "new_password": "Senha-nova-de-teste-1"}
    assert client.post("/api/auth/password", json=strong, headers=headers).status_code == 204
    client.cookies.clear()
    old = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin"}, headers=origin
    )
    assert old.status_code == 401
    again = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Senha-nova-de-teste-1"},
        headers=origin,
    )
    assert again.status_code == 200 and again.json()["user"]["must_change_password"] is False
    assert client.get("/api/users").status_code == 200
