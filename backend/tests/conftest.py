import ipaddress
import shutil
from collections import namedtuple
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import PROJECT_ROOT, Settings
from app.main import create_app
from app.network import routes as network_routes
from app.ops.backup import BackupManager
from app.ops.storage import GB

DiskUsage = namedtuple("DiskUsage", "total used free")


@pytest.fixture(autouse=True)
def roomy_disk(monkeypatch):
    """Backups see a simulated 1 TB disk with 900 GB free, so the storage limits (A3) do not
    depend on the machine running the tests. test_storage.py simulates small and full disks."""
    monkeypatch.setattr(
        BackupManager,
        "disk_usage",
        staticmethod(lambda _path: DiskUsage(1000 * GB, 100 * GB, 900 * GB)),
    )


@pytest.fixture(autouse=True)
def store_address(monkeypatch):
    """The in-process server is the main computer at 192.168.0.10 on the store network (the
    address the station tests use), whatever addresses the machine running the tests has: the
    local CA vouches only for the networks this computer is on (SEC-P1E-04). Real-server tests
    (test_network_server.py, E2E) use the machine's own address."""
    found = [ipaddress.ip_address(a) for a in ("127.0.0.1", "::1", "192.168.0.10")]
    monkeypatch.setattr(network_routes, "private_addresses", lambda _extra=None: list(found))


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
def client(migrated_config, tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=migrated_config.attributes["database_url"],
        # Generated documents must never land in the real data directory.
        document_directory=tmp_path / "documents",
        fiscal_directory=tmp_path / "fiscal",
        import_directory=tmp_path / "imports",
        backup_directory=tmp_path / "backups",
        backup_scheduler=False,
    )
    with TestClient(create_app(settings)) as client:
        yield client
