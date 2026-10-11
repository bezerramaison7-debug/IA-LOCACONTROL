from pathlib import Path

import pytest
from alembic import command
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import PROJECT_ROOT, Settings
from app.persistence.database import build_engine, resolve_database_url


def test_migration_upgrade_idempotency_downgrade_and_reupgrade(migration_config):
    url = migration_config.attributes["database_url"]
    command.upgrade(migration_config, "head")
    command.upgrade(migration_config, "head")
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            assert MigrationContext.configure(connection).get_current_heads() == ("0005_quotes",)
            assert set(inspect(connection).get_table_names()) == {
                "alembic_version",
                "users",
                "roles",
                "permissions",
                "user_roles",
                "role_permissions",
                "auth_sessions",
                "login_throttles",
                "audit_logs",
                "customers",
                "customer_addresses",
                "products",
                "equipment",
                "stock_movements",
                "prices",
                "import_batches",
                "import_origins",
                "quotes",
                "quote_items",
                "quote_transitions",
            }
            assert connection.scalar(text("SELECT COUNT(*) FROM roles")) == 5
            assert connection.scalar(text("SELECT COUNT(*) FROM users")) == 0
        command.check(migration_config)
        command.downgrade(migration_config, "base")
        with engine.connect() as connection:
            assert MigrationContext.configure(connection).get_current_heads() == ()
        command.upgrade(migration_config, "head")
        with engine.connect() as connection:
            assert MigrationContext.configure(connection).get_current_heads() == ("0005_quotes",)
    finally:
        engine.dispose()


def test_sqlite_enforces_foreign_keys(tmp_path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'foreign_keys.db').as_posix()}")
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
            connection.execute(
                text("CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id REFERENCES parent(id))")
            )
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text("INSERT INTO child (id, parent_id) VALUES (1, 999)"))
    finally:
        engine.dispose()


def test_relative_database_path_is_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    url = resolve_database_url("sqlite:///./data/locacontrol.db")
    assert Path(url.database) == PROJECT_ROOT / "data" / "locacontrol.db"


def test_non_sqlite_url_is_not_rewritten():
    url = "postgresql+psycopg://localhost/locacontrol"
    assert str(resolve_database_url(url)) == url


def test_environment_overrides_settings(monkeypatch):
    monkeypatch.setenv("LOCACONTROL_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("LOCACONTROL_CORS_ORIGINS", '["http://localhost:9999"]')
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite:///:memory:"
    assert settings.cors_origins == ["http://localhost:9999"]


def test_settings_reads_utf8_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("LOCACONTROL_DATABASE_URL=sqlite:///./data/configured.db\n", encoding="utf-8")
    settings = Settings(_env_file=env)
    assert settings.database_url == "sqlite:///./data/configured.db"
