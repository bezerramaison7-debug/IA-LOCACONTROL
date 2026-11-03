# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
"""Falha de backup não corrompe dados nem bloqueia a operação comercial (P1-E): disco cheio no
meio da gravação, falha na cópia do banco, trava liberada, nenhum arquivo parcial e retomada."""

import errno
import sqlite3
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from test_backups import manager
from test_quotes import admin, customer, switch  # noqa: F401

from app.core.clock import BUSINESS_TZ
from app.ops import backup as backup_module
from app.ops.backup import OPERATION_LOCK, BackupScheduler


def leftovers(client) -> list[str]:
    directory = Path(client.app.state.settings.backup_directory)
    if not directory.exists():
        return []
    return [p.name for p in directory.iterdir() if p.name.endswith((".part", ".db", ".zip"))]


def assert_business_as_usual(client, admin, document):
    # A trava foi liberada, o banco está íntegro e uma escrita comercial passa na hora.
    assert OPERATION_LOCK.acquire(blocking=False)
    OPERATION_LOCK.release()
    assert client.app.state.gate.maintenance is False
    database = manager(client).database_path()
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()
    customer(client, admin, document)


@pytest.mark.parametrize("stage", ["zip", "database"])
def test_disk_full_in_the_middle_of_a_backup_leaves_nothing_behind(
    client, admin, monkeypatch, stage
):
    customer(client, admin, "52998224725")
    if stage == "zip":
        real = zipfile.ZipFile.write

        def full(self, *args, **kwargs):
            real(self, *args, **kwargs)
            raise OSError(errno.ENOSPC, "No space left on device")

        monkeypatch.setattr(zipfile.ZipFile, "write", full)
    else:
        real_connect = sqlite3.connect

        class Broken:
            """A source connection whose online backup fails (disk I/O error)."""

            def __init__(self, *args, **kwargs):
                self.inner = real_connect(*args, **kwargs)

            def backup(self, *args, **kwargs):
                raise sqlite3.OperationalError("disk I/O error")

            def __getattr__(self, name):
                return getattr(self.inner, name)

        class Shim:
            Error, OperationalError, DatabaseError = (
                sqlite3.Error,
                sqlite3.OperationalError,
                sqlite3.DatabaseError,
            )

            @staticmethod
            def connect(*args, **kwargs):
                return Broken(*args, **kwargs)

        monkeypatch.setattr(backup_module, "sqlite3", Shim)
    switch(client, admin)
    response = client.post("/api/backups", headers=admin[1])
    monkeypatch.undo()
    assert response.status_code == 500
    assert leftovers(client) == []
    run = manager(client).history()["runs"][0]
    assert run["status"] == "failed" and run["error"]
    assert_business_as_usual(client, admin, "11144477735")


def test_scheduler_keeps_going_after_failures_and_recovers(client, admin, monkeypatch):
    switch(client, admin)
    config = {
        "enabled": True,
        "frequency": "20min",
        "time": "22:00",
        "keep": 14,
        "directory": "",
        "mirror_directory": "",
    }
    assert client.put("/api/backups/config", json=config, headers=admin[1]).status_code == 200
    scheduler = BackupScheduler(manager(client))
    now = datetime.now(BUSINESS_TZ)
    # Só esta troca é desfeita depois (monkeypatch.undo() desfaria também o disco simulado).
    with monkeypatch.context() as broken:
        broken.setattr(
            backup_module.BackupManager,
            "_create",
            lambda self, config, kind: (_ for _ in ()).throw(OSError(errno.EIO, "I/O error")),
        )
        with pytest.raises(HTTPException) as failed:
            scheduler.tick(now)
    assert failed.value.status_code == 500
    assert_business_as_usual(client, admin, "11144477735")
    made = scheduler.tick(now + timedelta(minutes=6))  # passada a espera, tenta de novo
    assert made and made["kind"] == "auto"
    assert manager(client).history()["runs"][0]["status"] == "ok"
