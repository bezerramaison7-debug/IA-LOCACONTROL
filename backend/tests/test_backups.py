# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
import hashlib
import json
import sqlite3
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_contracts import confirmed
from test_quotes import HEADERS, PASSWORD, admin, base, customer, line, login, switch  # noqa: F401

from app.auth.models import AuditLog
from app.core.clock import BUSINESS_TZ
from app.ops.backup import BackupManager, BackupScheduler, due


def manager(client) -> BackupManager:
    return BackupManager(client.app.state.settings, client.app.state.engine)


def backup(client, admin):
    switch(client, admin)
    response = client.post("/api/backups", headers=admin[1])
    assert response.status_code == 201, response.text
    return response.json()


def document(client, admin, person, item):
    contract = confirmed(client, admin, person, [line(item["id"])])
    response = client.post(f"/api/contracts/{contract['id']}/documents", json={}, headers=admin[1])
    assert response.status_code == 201
    return response.json()


def stored_documents(client) -> list[str]:
    folder = Path(client.app.state.settings.document_directory)
    return sorted(p.name for p in folder.glob("*.pdf")) if folder.is_dir() else []


def test_backup_set_contains_database_files_and_manifest(client, admin, base):
    person, item = base
    document(client, admin, person, item)
    created = backup(client, admin)
    assert created["revision"] == "0010_backups" and created["kind"] == "manual"
    overview = client.get("/api/backups").json()
    assert [entry["name"] for entry in overview["items"]] == [created["name"]]
    assert overview["config"]["enabled"] is False and overview["config"]["keep"] == 14
    archive = client.get(f"/api/backups/{created['name']}/download")
    assert archive.status_code == 200 and archive.content.startswith(b"PK")
    with zipfile.ZipFile(BytesIO(archive.content)) as content:
        names = content.namelist()
        manifest = json.loads(content.read("manifest.json"))
        database = content.read("locacontrol.db")
    assert "locacontrol.db" in names and "manifest.json" in names
    assert [n for n in names if n.startswith("documents/")] == [
        "documents/" + stored_documents(client)[0]
    ]
    assert manifest["revision"] == "0010_backups" and manifest["format"] == 1
    assert manifest["files"]["locacontrol.db"] == hashlib.sha256(database).hexdigest()
    report = client.post(f"/api/backups/{created['name']}/verify", headers=admin[1]).json()
    assert report["ok"] is True and report["users"] == 1 and report["files"] == 2

    path = Path(overview["directory"]) / created["name"]
    path.write_bytes(path.read_bytes()[:-200] + b"x" * 200)
    broken = client.post(f"/api/backups/{created['name']}/verify", headers=admin[1]).json()
    assert broken["ok"] is False and broken["errors"]
    for name in ("..%2F..%2Fdata%2Flocacontrol.db", "locacontrol.db", "locacontrol_x.zip"):
        assert client.get(f"/api/backups/{name}/download").status_code == 404
    client.cookies.clear()
    assert client.get("/api/backups").status_code == 401


def test_restore_needs_strong_confirmation_and_recovers_everything(client, admin, base):
    person, item = base
    document(client, admin, person, item)
    kept_documents = stored_documents(client)
    created = backup(client, admin)
    name = created["name"]
    later = customer(client, admin, "11144477735")
    document(client, admin, later, item)
    assert len(stored_documents(client)) == 2
    restore = f"/api/backups/{name}/restore"

    def attempt(confirmation, password):
        return client.post(
            restore, json={"confirmation": confirmation, "password": password}, headers=admin[1]
        )

    assert attempt("RESTAURAR", PASSWORD).status_code == 422
    assert attempt(f"restaurar {name}", PASSWORD).status_code == 422
    assert attempt(f"RESTAURAR {name}", "senha-errada").status_code == 403
    assert client.get("/api/customers").json()["total"] == 2  # nada mudou até aqui
    done = attempt(f"RESTAURAR {name}", PASSWORD)
    assert done.status_code == 200, done.text
    result = done.json()
    assert result["restored"] == name and result["upgraded_to"] is None
    assert result["safety_backup"].endswith("_pre-restore.zip")

    assert client.get("/health").json()["status"] == "ok"
    client.cookies.clear()
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    )
    assert response.status_code == 200
    customers = client.get("/api/customers").json()
    assert customers["total"] == 1 and customers["items"][0]["document"] == person["document"]
    assert client.get("/api/contracts").json()["total"] == 1
    assert stored_documents(client) == kept_documents
    backups = manager(client)
    directory = Path(client.app.state.settings.backup_directory)
    names = [entry["name"] for entry in backups.listing({"directory": ""})]
    assert result["safety_backup"] in names and name in names
    # Os arquivos posteriores ao backup foram movidos, não apagados.
    moved = list((directory / result["replaced_files"] / "documents").glob("*.pdf"))
    assert len(moved) == 2
    # A cópia de segurança guarda o estado anterior à restauração, com os dois clientes.
    safety = backups.verify(directory / result["safety_backup"])
    assert safety["ok"] and safety["kind"] == "pre-restore"
    with zipfile.ZipFile(directory / result["safety_backup"]) as content:
        scratch = directory / "inspect.db"
        scratch.write_bytes(content.read("locacontrol.db"))
    connection = sqlite3.connect(scratch)
    assert connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 2
    connection.close()
    with Session(client.app.state.engine) as db:
        entry = db.scalar(select(AuditLog).where(AuditLog.action == "backup.restored"))
        assert entry.actor_label == "admin" and entry.entity_id == name


def test_restore_refuses_a_set_from_an_unknown_version(client, admin, base):
    created = backup(client, admin)
    directory = Path(client.app.state.settings.backup_directory)
    original = directory / created["name"]
    scratch = directory / "future.db"
    with zipfile.ZipFile(original) as content:
        scratch.write_bytes(content.read("locacontrol.db"))
    connection = sqlite3.connect(scratch)
    connection.execute("UPDATE alembic_version SET version_num = '9999_future'")
    connection.commit()
    connection.close()
    future = "locacontrol_2030-01-01_000000.zip"
    data = scratch.read_bytes()
    with zipfile.ZipFile(directory / future, "w") as content:
        content.writestr("locacontrol.db", data)
        content.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": 1,
                    "revision": "9999_future",
                    "files": {"locacontrol.db": hashlib.sha256(data).hexdigest()},
                }
            ),
        )
    response = client.post(
        f"/api/backups/{future}/restore",
        json={"confirmation": f"RESTAURAR {future}", "password": PASSWORD},
        headers=admin[1],
    )
    assert response.status_code == 409 and "versão mais nova" in response.json()["detail"]
    assert client.get("/health").json()["status"] == "ok"
    names = [entry["name"] for entry in manager(client).listing({"directory": ""})]
    assert not any(n.endswith("_pre-restore.zip") for n in names)  # nada foi tocado


def test_configuration_schedule_and_retention(client, admin):
    def configure(**values):
        payload = {"enabled": True, "time": "22:00", "keep": 2, "directory": "", **values}
        return client.put("/api/backups/config", json=payload, headers=admin[1])

    assert configure(time="25:00").status_code == 422
    assert configure(keep=0).status_code == 422
    assert configure(directory="pasta-relativa").status_code == 422
    saved = configure()
    assert saved.status_code == 200 and saved.json()["config"]["keep"] == 2
    config = saved.json()["config"]

    night = datetime(2026, 10, 11, 22, 0, tzinfo=BUSINESS_TZ)
    assert due(config, night.replace(hour=21, minute=59), []) is False
    assert due(config, night, []) is True
    assert due(config, night, ["locacontrol_2026-10-10_220000.zip"]) is True
    # Um backup manual feito de manhã não substitui o automático da noite.
    assert due(config, night, ["locacontrol_2026-10-11_090000.zip"]) is True
    assert due(config, night, ["locacontrol_2026-10-11_220000.zip"]) is False
    assert due(config, night, ["locacontrol_2026-10-11_090000_pre-restore.zip"]) is True
    assert due({**config, "enabled": False}, night, []) is False

    backups = manager(client)
    scheduler = BackupScheduler(backups)
    assert scheduler.tick(night.replace(hour=8)) is None
    # O horário configurado passa a ser 00:00: o backup do dia é devido a qualquer hora.
    assert configure(time="00:00").status_code == 200
    automatic = scheduler.tick()
    assert automatic["kind"] == "auto"
    assert scheduler.tick() is None
    config = client.get("/api/backups").json()["config"]

    directory = Path(client.app.state.settings.backup_directory)
    for name in (
        "locacontrol_2020-01-01_220000.zip",
        "locacontrol_2020-01-02_220000.zip",
        "locacontrol_2020-01-03_220000_pre-restore.zip",
        "anotacoes.txt",
    ):
        (directory / name).write_bytes(b"old")
    backups.prune(config)
    remaining = sorted(p.name for p in directory.iterdir())
    assert remaining == sorted(
        [
            automatic["name"],
            "locacontrol_2020-01-02_220000.zip",
            "locacontrol_2020-01-03_220000_pre-restore.zip",
            "anotacoes.txt",
        ]
    )


def test_only_administrators_manage_backups(client, admin):
    created = backup(client, admin)
    worker = login(client, "worker", "COMERCIAL")
    assert client.get("/api/backups").status_code == 403
    assert client.post("/api/backups", headers=worker[1]).status_code == 403
    assert client.get(f"/api/backups/{created['name']}/download").status_code == 403
    restore = client.post(
        f"/api/backups/{created['name']}/restore",
        json={"confirmation": f"RESTAURAR {created['name']}", "password": PASSWORD},
        headers=worker[1],
    )
    assert restore.status_code == 403


def test_verification_rejects_sets_that_do_not_match_their_manifest(client, admin, base):
    created = backup(client, admin)
    directory = Path(client.app.state.settings.backup_directory)
    with zipfile.ZipFile(directory / created["name"]) as content:
        database = content.read("locacontrol.db")
        manifest = json.loads(content.read("manifest.json"))

    def forged(name, files, extra=None):
        with zipfile.ZipFile(directory / name, "w") as content:
            content.writestr("locacontrol.db", database)
            for member, data in (extra or {}).items():
                content.writestr(member, data)
            content.writestr("manifest.json", json.dumps({**manifest, "files": files}))
        return manager(client).verify(directory / name)

    empty = forged("locacontrol_2031-01-01_000000.zip", {})
    assert empty["ok"] is False and any("manifesto" in error for error in empty["errors"])
    planted = forged(
        "locacontrol_2031-01-02_000000.zip",
        manifest["files"],
        {"documents/plantado.pdf": b"%PDF-falso"},
    )
    assert planted["ok"] is False and any("fora do manifesto" in e for e in planted["errors"])
    restore = client.post(
        "/api/backups/locacontrol_2031-01-02_000000.zip/restore",
        json={
            "confirmation": "RESTAURAR locacontrol_2031-01-02_000000.zip",
            "password": PASSWORD,
        },
        headers=admin[1],
    )
    assert restore.status_code == 409
    assert manager(client).verify(directory / created["name"])["ok"] is True
