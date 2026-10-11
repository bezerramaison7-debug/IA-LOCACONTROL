import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import PROJECT_ROOT, Settings
from app.main import create_app


@pytest.fixture
def tmp_path():
    """Use a workspace-local temporary directory; global Windows temp may be ACL-restricted."""
    root = Path(__file__).resolve().parents[2] / ".test-tmp"
    path = root / uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def migration_config(tmp_path):
    config = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    config.attributes["database_url"] = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    return config


@pytest.fixture
def migrated_config(migration_config):
    command.upgrade(migration_config, "head")
    return migration_config


@pytest.fixture
def client(migrated_config):
    settings = Settings(_env_file=None, database_url=migrated_config.attributes["database_url"])
    with TestClient(create_app(settings)) as client:
        yield client
