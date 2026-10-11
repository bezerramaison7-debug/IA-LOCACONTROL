from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.main import create_app


def test_health_requires_database_and_current_schema(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "schema": "ok",
        "version": "0.1.0",
    }
    assert response.headers["cache-control"] == "no-store"


def test_unmigrated_database_is_not_healthy(migration_config):
    settings = Settings(_env_file=None, database_url=migration_config.attributes["database_url"])
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["schema"] == "outdated"


def test_unknown_revision_is_not_healthy(client):
    with client.app.state.engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'unknown_revision'"))
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["schema"] == "outdated"


def test_database_failure_is_503_without_sensitive_details(client, monkeypatch):
    def fail_connect():
        raise OperationalError("secret sql", {}, Exception("private database path"))

    monkeypatch.setattr(client.app.state.engine, "connect", fail_connect)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    assert "private" not in response.text
    assert "secret" not in response.text


def test_cors_allows_configured_origin(client):
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_does_not_allow_arbitrary_origin(client):
    response = client.get("/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


def test_unknown_api_is_not_a_successful_html_response(client):
    response = client.get("/api/resource-does-not-exist")
    assert response.status_code == 404


def test_openapi_documents_health(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "503" in response.json()["paths"]["/health"]["get"]["responses"]
