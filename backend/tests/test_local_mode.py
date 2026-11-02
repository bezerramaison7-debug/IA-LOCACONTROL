"""Local edition (ADR-023): no login, automatic session for this computer only."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.local import LOCAL_OPERATOR
from app.auth.models import AuditLog, User
from app.contracts.models import AppSetting
from app.core.config import Settings
from app.main import create_app

APP = {"X-LocaControl-Request": "1"}
HEADERS = {"Origin": "http://localhost:5173", **APP}
THIS_COMPUTER = {"base_url": "http://127.0.0.1:8000", "client": ("127.0.0.1", 50000)}
CUSTOMER = {
    "person_type": "PF",
    "legal_name": "Maria Locatária",
    "document": "52998224725",
    "addresses": [
        {"street": "Rua Um, 20", "city": "São Paulo", "state": "SP", "postal_code": "01001000"}
    ],
}


@pytest.fixture
def make_settings(migrated_config, tmp_path):
    def build(local_mode=True):
        return Settings(
            _env_file=None,
            local_mode=local_mode,
            database_url=migrated_config.attributes["database_url"],
            document_directory=tmp_path / "documents",
            fiscal_directory=tmp_path / "fiscal",
            import_directory=tmp_path / "imports",
            backup_directory=tmp_path / "backups",
            backup_scheduler=False,
        )

    return build


@pytest.fixture
def local_client(make_settings):
    with TestClient(create_app(make_settings()), **THIS_COMPUTER) as client:
        yield client


def enter(client) -> dict:
    response = client.get("/api/auth/me", headers=APP)
    assert response.status_code == 200, response.text
    return {**HEADERS, "X-CSRF-Token": response.json()["csrf_token"]}


def operators(client) -> int:
    with Session(client.app.state.engine) as db:
        return db.scalar(select(func.count()).where(User.username == LOCAL_OPERATOR))


def test_me_opens_local_session_and_reuses_the_operator(local_client):
    first = local_client.get("/api/auth/me", headers=APP)
    assert first.status_code == 200
    body = first.json()
    assert body["edition"] == "local" and len(body["installation_id"]) == 36
    assert body["user"]["username"] == LOCAL_OPERATOR
    assert body["user"]["must_change_password"] is False
    assert not [p for p in body["user"]["permissions"] if p.split(".")[0] in {"users", "roles"}]
    assert "customers.write" in body["user"]["permissions"]
    cookie = first.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
    assert first.headers["x-locacontrol-edition"] == "local"
    # Same cookie: same session, nothing new is set.
    again = local_client.get("/api/auth/me", headers=APP)
    assert again.json()["csrf_token"] == body["csrf_token"] and "set-cookie" not in again.headers
    local_client.cookies.clear()
    assert local_client.get("/api/auth/me", headers=APP).status_code == 200
    assert operators(local_client) == 1


def test_installation_id_survives_restarts(make_settings):
    ids = []
    for local_mode in (False, True, True):
        app = create_app(make_settings(local_mode))
        with TestClient(app, **THIS_COMPUTER) as client:
            with Session(client.app.state.engine) as db:
                ids.append(db.get(AppSetting, "installation").value["id"])
            if local_mode:
                ids.append(client.get("/api/auth/me", headers=APP).json()["installation_id"])
    assert len(set(ids)) == 1


def test_commercial_operation_without_login_is_audited_as_local_operator(local_client):
    headers = enter(local_client)
    created = local_client.post("/api/customers", json=CUSTOMER, headers=headers)
    assert created.status_code == 201, created.text
    installation = local_client.get("/api/auth/me", headers=APP).json()["installation_id"]
    with Session(local_client.app.state.engine) as db:
        entry = db.scalars(select(AuditLog).where(AuditLog.entity == "customers")).one()
        operator = db.scalar(select(User).where(User.username == LOCAL_OPERATOR))
    assert entry.actor_id == operator.id
    assert entry.actor_label == f"operador local · instalação {installation[:8]}"
    audit = local_client.get("/api/audit-logs")
    assert audit.status_code == 200 and audit.json()["items"][0]["actor"] == entry.actor_label


def test_cross_site_protection_is_unchanged(local_client):
    headers = enter(local_client)
    no_csrf = {k: v for k, v in headers.items() if k != "X-CSRF-Token"}
    assert local_client.post("/api/customers", json=CUSTOMER, headers=no_csrf).status_code == 403
    foreign = {**headers, "Origin": "http://evil.example"}
    assert local_client.post("/api/customers", json=CUSTOMER, headers=foreign).status_code == 403
    no_app_header = {k: v for k, v in headers.items() if k != "X-LocaControl-Request"}
    assert (
        local_client.post("/api/customers", json=CUSTOMER, headers=no_app_header).status_code == 403
    )


@pytest.mark.parametrize(
    ("options", "headers"),
    [
        ({"base_url": "http://127.0.0.1:8000", "client": ("192.168.0.20", 50000)}, APP),
        ({"base_url": "http://loja.example:8000", "client": ("127.0.0.1", 50000)}, APP),
        (THIS_COMPUTER, {}),
        (THIS_COMPUTER, {**APP, "Origin": "http://evil.example"}),
    ],
    ids=["other-computer", "dns-rebinding-host", "no-app-header", "foreign-origin"],
)
def test_no_automatic_session_outside_this_computer(make_settings, options, headers):
    with TestClient(create_app(make_settings()), **options) as client:
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.headers["x-locacontrol-edition"] == "local"
        assert "set-cookie" not in response.headers
        assert client.get("/api/customers").status_code == 401
        assert operators(client) == 1  # created at startup, no session handed out


DISABLED = [
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/password"),
    ("PATCH", "/api/auth/me"),
    ("GET", "/api/users"),
    ("POST", "/api/users"),
    ("PATCH", "/api/users/1"),
    ("POST", "/api/users/1/reset-password"),
    ("GET", "/api/users/1/customer"),
    ("PUT", "/api/users/1/customer"),
    ("GET", "/api/roles"),
    ("PUT", "/api/roles/1/permissions"),
    ("GET", "/api/permissions"),
    ("GET", "/api/portal/dashboard"),
    ("GET", "/api/portal/contracts"),
    ("POST", "/api/portal/renewal-requests"),
    ("GET", "/api/renewal-requests"),
    ("POST", "/api/renewal-requests/1/decide"),
]


def test_disabled_routes_answer_404(local_client):
    headers = enter(local_client)
    for method, path in DISABLED:
        response = local_client.request(method, path, json={}, headers=headers)
        assert response.status_code == 404, (method, path, response.text)
        # The guard answered, not a missing record.
        assert response.json()["detail"] == "Recurso indisponível na edição local."


def test_restore_without_password_needs_the_exact_phrase(local_client):
    headers = enter(local_client)
    assert local_client.post("/api/customers", json=CUSTOMER, headers=headers).status_code == 201
    name = local_client.post("/api/backups", headers=headers).json()["name"]
    restore = f"/api/backups/{name}/restore"
    wrong = local_client.post(restore, json={"confirmation": "RESTAURAR"}, headers=headers)
    assert wrong.status_code == 422
    done = local_client.post(restore, json={"confirmation": f"RESTAURAR {name}"}, headers=headers)
    assert done.status_code == 200, done.text
    assert done.json()["safety_backup"].endswith("_pre-restore.zip")
    with Session(local_client.app.state.engine) as db:
        entry = db.scalars(select(AuditLog).where(AuditLog.action == "backup.restored")).one()
    assert entry.actor_label.startswith("operador local · instalação ")
    # Sessions went back to the backup state; the app enters again by itself.
    local_client.cookies.clear()
    assert local_client.get("/api/auth/me", headers=APP).status_code == 200
    assert operators(local_client) == 1


def test_standard_edition_still_requires_login(make_settings):
    with TestClient(create_app(make_settings(local_mode=False)), **THIS_COMPUTER) as client:
        response = client.get("/api/auth/me", headers=APP)
        assert response.status_code == 401
        assert "x-locacontrol-edition" not in response.headers
        assert operators(client) == 0
        assert client.post("/api/auth/login", json={}, headers=HEADERS).status_code == 422
