# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
"""Integridade e recuperação: falhas no meio de operações, backup sob escrita, manutenção
durante a restauração, desfazer automático, outra instalação e encerramento abrupto."""

import hashlib
import shutil
import sqlite3
import subprocess
import sys
import threading
import zipfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_backups import backup, document, manager, stored_documents
from test_contracts import confirmed
from test_operations import (  # noqa: F401
    balances,
    by_code,
    call,
    run,
    stock_in,
    unit_status,
    withdrawal,
    world,
)
from test_quotes import (  # noqa: F401 — admin/base são fixtures reutilizadas
    HEADERS,
    PASSWORD,
    admin,
    base,
    customer,
    line,
    login,
    switch,
)

from app.auth.models import AuditLog, User
from app.contracts.models import ContractEvent, ItemUnit, Withdrawal, WithdrawalItem
from app.contracts.operations import OperationService
from app.contracts.schemas import WithdrawInput
from app.contracts.service import ContractService
from app.core.config import PROJECT_ROOT, Settings
from app.main import create_app
from app.masters.models import StockMovement
from app.ops import backup as backup_module
from app.ops.maintenance import MESSAGE

TRACKED = (StockMovement, Withdrawal, WithdrawalItem, ItemUnit, AuditLog, ContractEvent)


def counts(engine) -> dict:
    with Session(engine) as db:
        return {m.__name__: db.scalar(select(func.count()).select_from(m)) for m in TRACKED}


def installation(root: Path) -> Settings:
    """Banco migrado e pastas próprias, todos dentro da pasta temporária do teste."""
    url = f"sqlite:///{(root / 'locacontrol.db').as_posix()}"
    config = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    return Settings(
        _env_file=None,
        database_url=url,
        document_directory=root / "documents",
        fiscal_directory=root / "fiscal",
        import_directory=root / "imports",
        backup_directory=root / "backups",
        backup_scheduler=False,
    )


def relogin(client):
    client.cookies.clear()
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    )
    assert response.status_code == 200, response.text
    return {**HEADERS, "X-CSRF-Token": response.json()["csrf_token"]}


def restore(client, auth_headers, name):
    return client.post(
        f"/api/backups/{name}/restore",
        json={"confirmation": f"RESTAURAR {name}", "password": PASSWORD},
        headers=auth_headers,
    )


def tree(folder: Path) -> dict:
    if not folder.is_dir():
        return {}
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in folder.rglob("*")
        if p.is_file()
    }


# ---- operações -------------------------------------------------------------------------


def test_failure_in_the_middle_of_a_withdrawal_leaves_no_trace(client, admin, world, monkeypatch):
    person, scaffold, generator, units = world
    contract = confirmed(
        client,
        admin,
        person,
        [line(scaffold["id"], "3.000", "SEMANAL", 1), line(generator["id"], "1.000", "DIARIA", 1)],
    )
    lines = [
        {"contract_item_id": by_code(contract, "AND-1")["id"], "quantity": "3.000"},
        {
            "contract_item_id": by_code(contract, "GER-1")["id"],
            "quantity": "1.000",
            "equipment_ids": [units[0]["id"]],
        },
    ]
    before = counts(client.app.state.engine)
    seen = []

    def crash(self, *_args, **_kwargs):
        # Estoque e unidade já foram movidos nesta transação; auditoria e commit ainda não.
        seen.append(self.db.scalar(select(func.count()).select_from(StockMovement)))
        raise RuntimeError("queda simulada no meio da retirada")

    monkeypatch.setattr(ContractService, "event", crash)
    switch(client, admin)
    with pytest.raises(RuntimeError, match="queda simulada"):
        client.post(
            f"/api/contracts/{contract['id']}/withdrawals",
            json=withdrawal(lines),
            headers=admin[1],
        )
    monkeypatch.undo()
    assert seen == [before["StockMovement"] + 2]
    assert counts(client.app.state.engine) == before
    assert balances(client, "AND-1")["DISPONIVEL"] == "10.000"
    assert unit_status(client, units[0]["id"]) == "DISPONIVEL"
    assert client.get(f"/api/contracts/{contract['id']}").json()["status"] == "AGUARDANDO_RETIRADA"
    # A trava de escrita foi liberada: a mesma retirada funciona em seguida.
    call(client, admin, contract["id"], "withdrawals", withdrawal(lines))


def test_success_is_answered_only_after_the_write_is_committed(client, admin, world, monkeypatch):
    person, scaffold, _generator, _units = world
    contract = confirmed(client, admin, person, [line(scaffold["id"], "2.000", "SEMANAL", 1)])
    lines = [{"contract_item_id": contract["items"][0]["id"], "quantity": "1.000"}]
    database = manager(client).database_path()

    def withdrawals():
        connection = sqlite3.connect(database)  # conexão nova, fora do processo do app
        try:
            return connection.execute("SELECT COUNT(*) FROM withdrawals").fetchone()[0]
        finally:
            connection.close()

    def failed_commit(_self):
        raise OperationalError("COMMIT", {}, Exception("disco cheio simulado"))

    monkeypatch.setattr(Session, "commit", failed_commit)
    call(client, admin, contract["id"], "withdrawals", withdrawal(lines), expected=503)
    monkeypatch.undo()
    assert withdrawals() == 0  # sem gravação, sem sucesso

    call(client, admin, contract["id"], "withdrawals", withdrawal(lines))
    assert withdrawals() == 1  # 201 recebido => já está no arquivo


# ---- backup concorrente ----------------------------------------------------------------


def snapshot_is_consistent(backups, path: Path, scratch: Path) -> int:
    """Confere o conjunto e devolve quantas retiradas ele contém."""
    assert backups.verify(path)["ok"]
    with zipfile.ZipFile(path) as archive:
        scratch.write_bytes(archive.read("locacontrol.db"))
    connection = sqlite3.connect(scratch)
    try:
        one = lambda sql: connection.execute(sql).fetchone()[0]  # noqa: E731
        assert one("PRAGMA integrity_check") == "ok"
        taken = one("SELECT COALESCE(SUM(quantity_milli), 0) FROM withdrawal_items")
        moved = one(
            "SELECT COALESCE(SUM(quantity_milli), 0) FROM stock_movements "
            "WHERE to_status = 'LOCADO' AND reason LIKE 'Retirada%'"
        )
        count = one("SELECT COUNT(*) FROM withdrawals")
        audited = one("SELECT COUNT(*) FROM audit_logs WHERE action = 'contract.withdrawn'")
        active = one("SELECT COUNT(*) FROM contracts WHERE status = 'ATIVO'")
        # Movimentos, itens, auditoria e status da mesma retirada aparecem juntos ou não aparecem.
        assert taken == moved and count == audited == active
        return count
    finally:
        connection.close()
        scratch.unlink()


def test_backup_taken_while_writing_is_a_consistent_state(client, admin, world, tmp_path):
    person, scaffold, _generator, _units = world
    stock_in(client, admin, scaffold["id"], "10.000")
    contracts = [
        confirmed(client, admin, person, [line(scaffold["id"], "1.000", "SEMANAL", 1)])
        for _ in range(12)
    ]
    backups = manager(client)
    scratch = tmp_path / "inspect.db"

    def payload(contract):
        return WithdrawInput(
            **withdrawal([{"contract_item_id": contract["items"][0]["id"], "quantity": "1.000"}])
        )

    def take_backup(n):
        config = {"directory": str(tmp_path / f"set-{n}"), "keep": 100}
        made = backups.create(config)
        return Path(config["directory"]) / made["name"]

    # Determinístico: retirada gravada mas não confirmada não entra no backup; confirmada entra.
    with Session(client.app.state.engine) as db:
        db.execute(text("BEGIN IMMEDIATE"))
        OperationService(db, db.get(User, admin[0])).withdraw(
            contracts[0]["id"], payload(contracts[0])
        )
        db.flush()
        assert snapshot_is_consistent(backups, take_backup("open"), scratch) == 0
        db.commit()
    assert snapshot_is_consistent(backups, take_backup("committed"), scratch) == 1

    # Concorrente: uma thread grava retiradas enquanto outra tira backups sem parar.
    done, sets = threading.Event(), []

    def writer():
        try:
            for contract in contracts[1:]:
                assert (
                    run(client, admin, lambda s, c=contract: s.withdraw(c["id"], payload(c))) == 201
                )
        finally:
            done.set()

    thread = threading.Thread(target=writer)
    thread.start()
    while not done.is_set():
        sets.append(take_backup(len(sets)))
    thread.join()
    sets.append(take_backup("final"))
    seen = [snapshot_is_consistent(backups, path, scratch) for path in sets]
    assert len(sets) >= 2 and seen == sorted(seen) and seen[-1] == 12


# ---- restauração -----------------------------------------------------------------------


def test_requests_during_restore_get_503_and_nothing_is_written(client, admin, base, monkeypatch):
    person, item = base
    created = backup(client, admin)
    customer(client, admin, "11144477735")
    original_move, probes = shutil.move, []

    def move(src, dst):
        if not probes:
            # O banco já foi sobrescrito e as pastas ainda não: ninguém pode ver este meio-termo.
            probes.append(client.get("/api/customers"))
            probes.append(
                client.post(
                    "/api/customers",
                    json={
                        "person_type": "PF",
                        "legal_name": "Durante a restauração",
                        "document": "39053344705",
                    },
                    headers=admin[1],
                )
            )
            probes.append(client.get("/health"))
        return original_move(src, dst)

    monkeypatch.setattr(backup_module.shutil, "move", move)
    switch(client, admin)
    done = restore(client, admin[1], created["name"])
    monkeypatch.undo()
    assert done.status_code == 200, done.text
    read, write, health = probes
    assert read.status_code == 503 and read.json() == {"detail": MESSAGE}
    assert write.status_code == 503 and read.headers["retry-after"] == "5"
    assert health.status_code == 503 and health.json()["status"] == "maintenance"
    # Depois da restauração o sistema volta a responder normalmente, com o estado do backup.
    assert client.get("/health").json()["status"] == "ok"
    relogin(client)
    customers = client.get("/api/customers").json()
    assert customers["total"] == 1 and customers["items"][0]["document"] == person["document"]


def test_restore_waits_for_requests_in_flight_and_gives_up_without_changes(client, admin, base):
    created = backup(client, admin)
    customer(client, admin, "11144477735")
    gate = client.app.state.gate
    gate.timeout = 0.2
    assert gate.enter()  # uma requisição ainda em andamento
    try:
        switch(client, admin)
        response = restore(client, admin[1], created["name"])
    finally:
        gate.leave()
    assert response.status_code == 409 and "Nada foi alterado" in response.json()["detail"]
    assert gate.maintenance is False
    assert client.get("/api/customers").json()["total"] == 2
    names = [entry["name"] for entry in client.get("/api/backups").json()["items"]]
    assert not any(n.endswith("_pre-restore.zip") for n in names)


def test_failure_after_database_overwrite_is_undone(client, admin, base, monkeypatch):
    person, item = base
    document(client, admin, person, item)
    created = backup(client, admin)
    later = customer(client, admin, "11144477735")
    document(client, admin, later, item)
    settings = client.app.state.settings
    files_before = tree(Path(settings.document_directory))
    database = manager(client).database_path()
    customers_before = client.get("/api/customers").json()
    assert customers_before["total"] == 2 and len(files_before) == 2
    original_move, calls = shutil.move, []

    def move(src, dst):
        calls.append(dst)
        # 1: coloca imports; 2: afasta documents; 3: coloca documents -> falha aqui.
        if len(calls) == 3:
            raise OSError("arquivo em uso (simulado)")
        return original_move(src, dst)

    monkeypatch.setattr(backup_module.shutil, "move", move)
    switch(client, admin)
    response = restore(client, admin[1], created["name"])
    monkeypatch.undo()
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "desfeita automaticamente" in detail and "nada foi alterado" in detail
    # Banco e pastas exatamente como antes; a sessão do administrador continua válida.
    connection = sqlite3.connect(database)
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    connection.close()
    assert client.get("/api/customers").json() == customers_before
    assert tree(Path(settings.document_directory)) == files_before
    assert not Path(settings.import_directory).exists()
    directory = Path(settings.backup_directory)
    assert not list(directory.glob("replaced_*")) and not list(directory.glob(".restore_*"))
    assert len(list(directory.glob("*_pre-restore.zip"))) == 1
    assert client.get("/health").json()["status"] == "ok"


def test_undo_failure_points_to_the_safety_copy(client, admin, base, monkeypatch):
    created = backup(client, admin)
    original_move, calls = shutil.move, []

    def move(src, dst):
        # A primeira pasta é colocada; depois disso nada mais se move, nem para desfazer.
        calls.append(dst)
        if len(calls) > 1:
            raise OSError("disco removido (simulado)")
        return original_move(src, dst)

    monkeypatch.setattr(backup_module.shutil, "move", move)
    switch(client, admin)
    response = restore(client, admin[1], created["name"])
    monkeypatch.setattr(backup_module.shutil, "move", original_move)
    assert response.status_code == 500
    detail = response.json()["detail"]
    safety = next(Path(client.app.state.settings.backup_directory).glob("*_pre-restore.zip"))
    assert "manualmente" in detail and safety.name in detail


def test_backup_restores_on_a_new_empty_installation(client, admin, base, tmp_path):
    person, item = base
    made = document(client, admin, person, item)
    created = backup(client, admin)
    source = Path(client.app.state.settings.backup_directory) / created["name"]

    other_settings = installation(tmp_path / "outra-maquina")
    with TestClient(create_app(other_settings)) as other:
        local = login(other, "admin", "ADMINISTRADOR")  # conta da instalação nova
        Path(other_settings.backup_directory).mkdir(parents=True)
        shutil.copy2(source, Path(other_settings.backup_directory) / created["name"])
        assert other.get("/api/customers").json()["total"] == 0
        response = restore(other, local[1], created["name"])
        assert response.status_code == 200, response.text
        relogin(other)  # agora valem as contas que vieram no backup
        customers = other.get("/api/customers").json()
        assert customers["total"] == 1 and customers["items"][0]["document"] == person["document"]
        assert other.get("/api/contracts").json()["total"] == 1
        pdf = other.get(f"/api/contracts/documents/{made['id']}/download")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        assert hashlib.sha256(pdf.content).hexdigest() == made["checksum"]
        assert sorted(p.name for p in Path(other_settings.document_directory).glob("*.pdf")) == (
            stored_documents(client)
        )


# ---- encerramento abrupto --------------------------------------------------------------

CRASH = """
import os, sqlite3, sys
connection = sqlite3.connect(sys.argv[1], isolation_level=None)
connection.execute("PRAGMA cache_size=10")  # força gravar páginas no arquivo antes do commit
connection.execute("BEGIN IMMEDIATE")
for n in range(400):
    connection.execute(
        "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, 0)",
        (f"crash-{n}", '{"x": "' + "y" * 500 + '"}'),
    )
if sys.argv[2] == "commit":
    connection.execute("COMMIT")
os._exit(1)
"""


@pytest.mark.parametrize("commit", [False, True])
def test_startup_after_abrupt_termination(tmp_path, commit):
    settings = installation(tmp_path / "queda")
    database = tmp_path / "queda" / "locacontrol.db"
    finished = subprocess.run(
        [sys.executable, "-c", CRASH, str(database), "commit" if commit else "no"], timeout=60
    )
    assert finished.returncode == 1
    journal = database.with_name(database.name + "-journal")
    # Sem commit fica um journal "quente": o arquivo do banco foi tocado pela metade.
    assert journal.exists() is not commit
    with TestClient(create_app(settings)) as app:
        health = app.get("/health")
        assert health.status_code == 200 and health.json()["status"] == "ok"
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        rows = connection.execute(
            "SELECT COUNT(*) FROM app_settings WHERE key LIKE 'crash-%'"
        ).fetchone()[0]
    finally:
        connection.close()
    assert rows == (400 if commit else 0)
    assert not journal.exists()
