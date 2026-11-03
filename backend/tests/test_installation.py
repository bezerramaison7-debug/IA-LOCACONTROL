"""P1-B: program and data folders, packaged resources, server entry point, single instance."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app import server
from app.core import config as config_module
from app.core.config import PROJECT_ROOT, Settings, data_root, resource


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    path = tmp_path / "Dados Locação Ç"  # spaces and accents on purpose
    monkeypatch.setenv("LOCACONTROL_DATA_DIR", str(path))
    for name in ("DATABASE_URL", "LOCAL_MODE", "BACKUP_DIRECTORY", "IMPORT_DIRECTORY"):
        monkeypatch.delenv(f"LOCACONTROL_{name}", raising=False)
    return path.resolve()


def revision(database: Path) -> str:
    connection = sqlite3.connect(database)
    try:
        return connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    finally:
        connection.close()


# ---- configuration ---------------------------------------------------------------------


def test_env_written_by_the_installer_with_a_bom_is_read(data_dir, monkeypatch):
    """Inno Setup grava o .env em UTF-8 com BOM; o python-dotenv o descarta (contrato daqui)."""
    monkeypatch.delenv("LOCACONTROL_NETWORK_MODE", raising=False)
    data_dir.mkdir(parents=True)
    (data_dir / ".env").write_bytes(
        b"\xef\xbb\xbfLOCACONTROL_LOCAL_MODE=true\r\nLOCACONTROL_NETWORK_MODE=true\r\n"
    )
    settings = Settings()
    assert settings.local_mode is True and settings.network_mode is True


def test_data_dir_moves_every_persistent_default(data_dir):
    settings = Settings(_env_file=None)
    assert settings.database_url == f"sqlite:///{(data_dir / 'locacontrol.db').as_posix()}"
    assert settings.import_directory == data_dir / "imports"
    assert settings.document_directory == data_dir / "documents"
    assert settings.fiscal_directory == data_dir / "fiscal"
    assert settings.backup_directory == data_dir / "backups"


def test_specific_variables_win_over_data_dir(data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCACONTROL_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("LOCACONTROL_BACKUP_DIRECTORY", str(tmp_path / "elsewhere"))
    settings = Settings(_env_file=None, fiscal_directory=tmp_path / "fiscal")
    assert settings.database_url == "sqlite:///:memory:"
    assert settings.backup_directory == tmp_path / "elsewhere"
    assert settings.fiscal_directory == tmp_path / "fiscal"
    assert settings.document_directory == data_dir / "documents"


def test_env_file_is_read_from_data_dir(data_dir):
    data_dir.mkdir(parents=True)
    (data_dir / ".env").write_text("LOCACONTROL_COMPANY_NAME=Loja Teste\n", encoding="utf-8")
    assert Settings().company_name == "Loja Teste"


def test_without_data_dir_nothing_changes(monkeypatch):
    monkeypatch.delenv("LOCACONTROL_DATA_DIR", raising=False)
    settings = Settings(_env_file=None)
    assert data_root() == PROJECT_ROOT / "data"
    assert config_module.env_file() == PROJECT_ROOT / ".env"
    assert settings.database_url == "sqlite:///./data/locacontrol.db"
    assert settings.backup_directory == PROJECT_ROOT / "data" / "backups"
    assert settings.import_directory == PROJECT_ROOT / "data" / "imports"


def test_frozen_resources_and_default_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.delenv("LOCACONTROL_DATA_DIR", raising=False)
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "ProgramData"))
    assert resource("backend/migrations") == tmp_path / "bundle" / "backend" / "migrations"
    assert resource("backend/alembic.ini") == tmp_path / "bundle" / "backend" / "alembic.ini"
    assert resource("frontend/dist") == tmp_path / "bundle" / "frontend" / "dist"
    assert data_root() == tmp_path / "ProgramData" / "LocaControl"
    settings = Settings(_env_file=None)
    assert settings.backup_directory == tmp_path / "ProgramData" / "LocaControl" / "backups"


def test_development_resources_are_in_the_project():
    assert resource("backend/alembic.ini").is_file()
    assert (resource("backend/migrations") / "env.py").is_file()


# ---- entry point -----------------------------------------------------------------------


def test_prepare_creates_migrated_database_in_empty_data_dir(data_dir, monkeypatch):
    monkeypatch.setenv("LOCACONTROL_LOCAL_MODE", "true")
    assert server.main(["--prepare"]) == 0
    assert revision(data_dir / "locacontrol.db") == "0013_audit_station"
    # New database: nothing to copy before migrating.
    assert not (data_dir / "backups").exists()
    connection = sqlite3.connect(data_dir / "locacontrol.db")
    try:
        # Local edition: no admin/admin account.
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    finally:
        connection.close()


def test_prepare_copies_old_database_before_migrating(data_dir, monkeypatch):
    monkeypatch.setenv("LOCACONTROL_LOCAL_MODE", "true")
    database = data_dir / "locacontrol.db"
    data_dir.mkdir(parents=True)
    old = Config(str(resource("backend/alembic.ini")))
    old.attributes["database_url"] = f"sqlite:///{database.as_posix()}"
    command.upgrade(old, "0009_fiscal")
    assert server.main(["--prepare"]) == 0
    copies = list((data_dir / "backups").glob("pre-upgrade-*.db"))
    assert len(copies) == 1 and revision(copies[0]) == "0009_fiscal"
    assert revision(database) == "0013_audit_station"
    # Already at head: no second copy.
    assert server.main(["--prepare"]) == 0
    assert len(list((data_dir / "backups").glob("pre-upgrade-*.db"))) == 1


def test_login_edition_still_creates_first_access_account(data_dir, monkeypatch):
    monkeypatch.setenv("LOCACONTROL_LOCAL_MODE", "false")
    assert server.prepare(Settings()) is True
    assert server.prepare(Settings()) is False


# ---- single instance -------------------------------------------------------------------


def test_second_lock_on_same_data_dir_fails_until_released(tmp_path):
    first = server.acquire_lock(tmp_path)
    try:
        with pytest.raises(server.AlreadyRunning, match="já está em execução"):
            server.acquire_lock(tmp_path)
    finally:
        first.close()
    server.acquire_lock(tmp_path).close()


def test_second_instance_exits_without_touching_database(data_dir, capsys):
    data_dir.mkdir(parents=True)
    lock = server.acquire_lock(data_dir)
    try:
        assert server.main(["--prepare"]) == server.EXIT_ALREADY_RUNNING
    finally:
        lock.close()
    assert "já está em execução" in capsys.readouterr().err
    assert not (data_dir / "locacontrol.db").exists()


def prepare_process(env):
    return subprocess.Popen(
        [sys.executable, "-m", "app.server", "--prepare"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "backend"), **env},
    )


def save_small_reserve(database: Path):
    """Processos à parte não veem o disco simulado do conftest: a instalação de teste grava a
    própria reserva (como em Gestão → Backups) para caber em máquinas de CI com pouco disco.
    A reserva padrão é testada em test_storage.py e na recusa por falta de espaço abaixo."""
    connection = sqlite3.connect(database)
    try:
        limits = {"max_total_gb": 10, "min_free_gb": 1, "margin_percent": 0, "margin_max_gb": 0}
        connection.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES ('backup', ?, 0)",
            (json.dumps(limits),),
        )
        connection.commit()
    finally:
        connection.close()


def test_simultaneous_starts_never_migrate_twice(data_dir):
    database = data_dir / "locacontrol.db"
    data_dir.mkdir(parents=True)
    old = Config(str(resource("backend/alembic.ini")))
    old.attributes["database_url"] = f"sqlite:///{database.as_posix()}"
    command.upgrade(old, "0009_fiscal")
    save_small_reserve(database)
    env = {"LOCACONTROL_DATA_DIR": str(data_dir), "LOCACONTROL_LOCAL_MODE": "true"}
    starts = [prepare_process(env) for _ in range(2)]
    codes = sorted(process.wait(timeout=120) for process in starts)
    # Either the second one found the lock taken, or it started after the first had finished.
    assert codes in ([0, 0], [0, server.EXIT_ALREADY_RUNNING]), [p.stderr.read() for p in starts]
    assert len(list((data_dir / "backups").glob("pre-upgrade-*.db"))) == 1
    assert revision(database) == "0013_audit_station"


# ---- unavailable data folder -----------------------------------------------------------


def test_first_installation_creates_data_dir_under_existing_parent(data_dir, monkeypatch):
    monkeypatch.setenv("LOCACONTROL_LOCAL_MODE", "true")
    assert not data_dir.exists()
    assert server.main(["--prepare"]) == 0
    assert (data_dir / "locacontrol.db").is_file() and (data_dir / server.MARKER).is_file()


def test_missing_parent_is_unavailable_not_a_new_install(tmp_path, monkeypatch, capsys):
    target = tmp_path / "unidade-ausente" / "LocaControl"
    monkeypatch.setenv("LOCACONTROL_DATA_DIR", str(target))
    assert server.main(["--prepare"]) == server.EXIT_DATA_UNAVAILABLE
    assert "indisponível" in capsys.readouterr().err
    assert not (tmp_path / "unidade-ausente").exists()


def test_file_in_place_of_data_dir_is_unavailable(tmp_path, monkeypatch, capsys):
    target = tmp_path / "dados"
    target.write_text("não é pasta", encoding="utf-8")
    monkeypatch.setenv("LOCACONTROL_DATA_DIR", str(target))
    assert server.main(["--prepare"]) == server.EXIT_DATA_UNAVAILABLE
    assert "não é uma pasta" in capsys.readouterr().err


def test_vanished_database_is_never_recreated(data_dir, monkeypatch, capsys):
    monkeypatch.setenv("LOCACONTROL_LOCAL_MODE", "true")
    assert server.main(["--prepare"]) == 0
    (data_dir / "locacontrol.db").unlink()
    assert server.main(["--prepare"]) == server.EXIT_DATA_UNAVAILABLE
    assert "não foi encontrado" in capsys.readouterr().err
    assert not (data_dir / "locacontrol.db").exists()


@pytest.mark.skipif(os.name != "nt", reason="ACL do Windows")
def test_data_dir_without_write_permission_is_unavailable(tmp_path, monkeypatch, capsys):
    parent = tmp_path / "sem-escrita"
    parent.mkdir()
    user = os.environ["USERNAME"]
    subprocess.run(["icacls", str(parent), "/deny", f"{user}:(OI)(CI)W"], check=True)
    try:
        monkeypatch.setenv("LOCACONTROL_DATA_DIR", str(parent / "LocaControl"))
        assert server.main(["--prepare"]) == server.EXIT_DATA_UNAVAILABLE
        assert "Sem permissão" in capsys.readouterr().err
    finally:
        subprocess.run(["icacls", str(parent), "/remove:d", user], check=True)
    assert not (parent / "LocaControl").exists()


def test_lock_is_released_when_holder_dies_abruptly(tmp_path):
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import os, sys; from pathlib import Path; from app.server import acquire_lock; "
            "held = acquire_lock(Path(sys.argv[1])); print('locked', flush=True); "
            "sys.stdin.readline(); os._exit(9)",
            str(tmp_path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "backend")},
    )
    try:
        assert holder.stdout.readline().strip() == "locked"
        with pytest.raises(server.AlreadyRunning):
            server.acquire_lock(tmp_path)
        holder.stdin.write("\n")
        holder.stdin.flush()
        assert holder.wait(timeout=15) == 9
    finally:
        if holder.poll() is None:
            holder.kill()
    server.acquire_lock(tmp_path).close()


# ---- pre-upgrade copy and free space (P1-E) ------------------------------------------------


def old_database(data_dir) -> Path:
    database = data_dir / "locacontrol.db"
    data_dir.mkdir(parents=True)
    old = Config(str(resource("backend/alembic.ini")))
    old.attributes["database_url"] = f"sqlite:///{database.as_posix()}"
    command.upgrade(old, "0009_fiscal")
    return database


def fake_disk(monkeypatch, free_for):
    """free_for(path) -> free GB on the disk of that path (1 TB disks)."""
    from collections import namedtuple

    from app.ops.backup import BackupManager
    from app.ops.storage import GB

    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(
        BackupManager,
        "disk_usage",
        staticmethod(lambda path: usage(1000 * GB, 0, free_for(Path(path)) * GB)),
    )


def test_pre_upgrade_copy_falls_back_to_the_data_folder_when_backups_are_full(
    data_dir, monkeypatch, tmp_path
):
    backups = tmp_path / "disco-cheio"
    backups.mkdir()
    monkeypatch.setenv("LOCACONTROL_LOCAL_MODE", "true")
    monkeypatch.setenv("LOCACONTROL_BACKUP_DIRECTORY", str(backups))
    database = old_database(data_dir)
    fake_disk(monkeypatch, lambda path: 5 if path.is_relative_to(backups) else 500)
    assert server.main(["--prepare"]) == 0
    assert not list(backups.glob("pre-upgrade-*.db"))
    copies = list(data_dir.glob("pre-upgrade-*.db"))
    assert len(copies) == 1 and revision(copies[0]) == "0009_fiscal"
    assert revision(database) == "0013_audit_station"


def test_without_room_for_the_copy_nothing_is_migrated_and_the_server_does_not_start(
    data_dir, monkeypatch, capsys
):
    monkeypatch.setenv("LOCACONTROL_LOCAL_MODE", "true")
    database = old_database(data_dir)
    before = database.read_bytes()
    fake_disk(monkeypatch, lambda path: 5)  # abaixo da reserva mínima de 10 GB em todo lugar
    assert server.main(["--prepare"]) == server.EXIT_NO_SPACE
    assert "Nada foi alterado" in capsys.readouterr().err
    assert database.read_bytes() == before and revision(database) == "0009_fiscal"
    assert not list(data_dir.rglob("pre-upgrade-*.db"))
    assert not (data_dir / server.MARKER).exists()
    fake_disk(monkeypatch, lambda path: 500)  # espaço liberado: inicia normalmente
    assert server.main(["--prepare"]) == 0
    assert revision(database) == "0013_audit_station"


def test_only_the_newest_pre_upgrade_copies_are_kept(tmp_path):
    for n in range(6):
        (tmp_path / f"pre-upgrade-2026110{n}-120000.db").write_bytes(b"x")
    (tmp_path / "locacontrol_2026-11-01_120000.zip").write_bytes(b"x")
    server.prune_pre_upgrade(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "locacontrol_2026-11-01_120000.zip",
        "pre-upgrade-20261103-120000.db",
        "pre-upgrade-20261104-120000.db",
        "pre-upgrade-20261105-120000.db",
    ]
