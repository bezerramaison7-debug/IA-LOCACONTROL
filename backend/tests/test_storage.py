# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
"""Limites de armazenamento dos backups (A3): teto da pasta, espaço mínimo livre no disco,
estimativa antes de gravar e retenção segura sob pressão, em discos pequenos e grandes."""

from collections import namedtuple
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from test_backups import backup, document, manager
from test_integrity import restore
from test_quotes import admin, base, customer, switch  # noqa: F401

from app.core.clock import BUSINESS_TZ
from app.ops.backup import BackupManager, BackupScheduler
from app.ops.storage import GB, LIMIT_DEFAULTS, plan, removal_order, reserve_bytes

Disk = namedtuple("Disk", "total used free")
CONFIG = {
    "enabled": True,
    "frequency": "20min",
    "time": "22:00",
    "keep": 14,
    "directory": "",
    "mirror_directory": "",
    **LIMIT_DEFAULTS,
}


def disk(monkeypatch, total_gb, free_gb, only=None):
    """Simulates the disk of every path, or only of the paths under `only`."""
    real = BackupManager.disk_usage

    def usage(path):
        if only is None or Path(path).resolve().is_relative_to(Path(only).resolve()):
            return Disk(total_gb * GB, (total_gb - free_gb) * GB, free_gb * GB)
        return real(path)

    monkeypatch.setattr(BackupManager, "disk_usage", staticmethod(usage))


def sparse(path: Path, size: int):
    """A set that looks large (st_size) without using the disk."""
    with path.open("wb") as handle:
        handle.truncate(size)


def stamp(when, suffix=""):
    return f"locacontrol_{when:%Y-%m-%d_%H%M%S}{suffix}.zip"


def test_reserve_is_the_larger_of_10_gb_and_15_percent_on_small_and_large_disks():
    assert reserve_bytes(32 * GB, LIMIT_DEFAULTS) == 10 * GB  # 15 % = 4,8 GB
    assert reserve_bytes(64 * GB, LIMIT_DEFAULTS) == 10 * GB  # 15 % = 9,6 GB
    assert reserve_bytes(256 * GB, LIMIT_DEFAULTS) == int(256 * GB * 15 // 100)
    assert reserve_bytes(2000 * GB, LIMIT_DEFAULTS) == 300 * GB
    assert reserve_bytes(2000 * GB, {**LIMIT_DEFAULTS, "min_free_percent": 0}) == 10 * GB

    def decide(total, free, estimate, managed=0, removable=(), bounded=True, **limits):
        return plan(
            estimate=estimate,
            peak=estimate * 3 // 2,
            free=free,
            disk_total=total,
            managed=managed,
            removable=list(removable),
            config={**LIMIT_DEFAULTS, **limits},
            bounded=bounded,
        )

    # Disco pequeno (64 GB, 12 GB livres): cabe 1 GB, não cabe 3 GB.
    assert decide(64 * GB, 12 * GB, 1 * GB).fits
    small = decide(64 * GB, 12 * GB, 3 * GB)
    assert not small.fits and "Espaço insuficiente" in small.reason and small.remove == []
    # Disco grande (2 TB): com 400 GB livres cabe; com 200 GB livres a reserva de 15 % (300 GB)
    # já não está garantida e nada é gravado.
    assert decide(2000 * GB, 400 * GB, 5 * GB, max_total_gb=50).fits
    assert not decide(2000 * GB, 200 * GB, 5 * GB, max_total_gb=50).fits
    # Teto: 9,5 GB ocupados + 1 GB passam de 10 GB; sai o que for necessário, na ordem dada.
    cap = decide(
        1000 * GB, 900 * GB, 1 * GB, managed=19 * GB // 2, removable=[("a", GB), ("b", GB)]
    )
    assert cap.fits and cap.remove == ["a"]
    blocked = decide(1000 * GB, 900 * GB, 1 * GB, managed=12 * GB)
    assert not blocked.fits and "limite de 10,0 GB" in blocked.reason
    # Recuperação (cópia antes de restaurar, importação) ignora o teto, nunca a reserva.
    assert decide(1000 * GB, 900 * GB, 1 * GB, managed=12 * GB, bounded=False).fits
    assert not decide(64 * GB, 11 * GB, 1 * GB, bounded=False).fits


def test_removal_order_keeps_the_newest_and_takes_intermediate_sets_first():
    rows = [
        ("d1-a", 1, "2026-11-01090000", False),
        ("d1-b", 1, "2026-11-01180000", True),
        ("d2-a", 1, "2026-11-02100000", False),
        ("d2-b", 1, "2026-11-02200000", True),
    ]
    assert [name for name, _ in removal_order(rows)] == ["d1-a", "d2-a", "d1-b"]
    assert removal_order(rows[:1]) == []  # a única cópia nunca sai


def test_backup_is_refused_before_writing_when_the_disk_would_go_below_the_reserve(
    client, admin, base, monkeypatch
):
    person, item = base
    document(client, admin, person, item)
    directory = Path(client.app.state.settings.backup_directory)
    disk(monkeypatch, total_gb=64, free_gb=10)  # já no limite de 10 GB livres
    switch(client, admin)
    response = client.post("/api/backups", headers=admin[1])
    assert response.status_code == 507 and "Espaço insuficiente" in response.json()["detail"]
    leftovers = [p.name for p in directory.iterdir()] if directory.exists() else []
    assert not [n for n in leftovers if n.endswith((".zip", ".part", ".db"))]
    history = manager(client).history()
    assert history["runs"][0]["status"] == "failed"
    status = client.get("/api/backups/status").json()
    assert status["alert"]["level"] == "danger"
    assert status["storage"]["fits"] is False and status["storage"]["reserve_bytes"] == 10 * GB
    # Disco grande e folgado: o mesmo backup passa e a estimativa aparece.
    disk(monkeypatch, total_gb=2000, free_gb=1500)
    made = backup(client, admin)
    storage = client.get("/api/backups/status").json()["storage"]
    assert storage["fits"] and storage["managed_bytes"] == made["size"]
    assert storage["estimate_bytes"] > 0 and storage["peak_bytes"] > storage["estimate_bytes"]


def test_cap_removes_old_intermediate_sets_first_and_never_the_newest_or_recovery_copies(
    client, admin, monkeypatch
):
    directory = Path(client.app.state.settings.backup_directory)
    directory.mkdir(parents=True)
    old = datetime.now(BUSINESS_TZ) - timedelta(days=3)
    names = {
        "intermediate": stamp(old.replace(hour=9)),
        "daily": stamp(old.replace(hour=18)),
        "newest": stamp(old + timedelta(days=1)),
        "pre_restore": stamp(old.replace(hour=10), "_pre-restore"),
    }
    for label, name in names.items():
        sparse(directory / name, 3 * GB if label != "pre_restore" else GB)
    switch(client, admin)
    config = {**CONFIG, "keep": 30, "max_total_gb": 10}
    assert client.put("/api/backups/config", json=config, headers=admin[1]).status_code == 200
    made = backup(client, admin)  # 10 GB ocupados + o novo passam do teto: sai a intermediária
    assert made["removed_for_space"] == [names["intermediate"]]
    left = {p.name for p in directory.iterdir()}
    assert {names["daily"], names["newest"], names["pre_restore"], made["name"]} <= left
    run = manager(client).history()["runs"][0]
    assert run["removed_for_space"] == [names["intermediate"]]

    # Cópias de restauração e importadas não saem: com elas ocupando o teto, o backup é recusado.
    for n in range(4):
        sparse(directory / stamp(old.replace(hour=11, minute=n), "_importado"), 3 * GB)
    response = client.post("/api/backups", headers=admin[1])
    assert response.status_code == 507 and "limite" in response.json()["detail"]
    assert {p.name for p in directory.iterdir()} >= left


def test_recovery_copies_ignore_the_cap_but_not_the_reserve(client, admin, base, monkeypatch):
    created = backup(client, admin)
    directory = Path(client.app.state.settings.backup_directory)
    sparse(directory / stamp(datetime(2020, 1, 1), "_importado"), 20 * GB)  # teto estourado
    switch(client, admin)
    # A restauração cria a cópia de segurança mesmo acima do teto.
    assert restore(client, admin[1], created["name"]).status_code == 200
    # Sem espaço no disco dos dados, a restauração é recusada antes de qualquer mudança.
    from test_integrity import relogin

    headers = relogin(client)
    before = client.get("/api/customers").json()
    disk(monkeypatch, total_gb=64, free_gb=10)
    response = restore(client, headers, created["name"])
    assert response.status_code == 507 and "Nada foi alterado" in response.json()["detail"]
    assert client.get("/api/customers").json() == before
    assert len(list(directory.glob("*_pre-restore.zip"))) == 1  # nenhuma nova cópia


def test_import_and_second_copy_respect_the_reserve(client, admin, monkeypatch, tmp_path):
    import io

    created = backup(client, admin)
    directory = Path(client.app.state.settings.backup_directory)
    content = (directory / created["name"]).read_bytes()
    (directory / created["name"]).unlink()
    mirror = tmp_path / "outro-disco"
    switch(client, admin)
    config = {**CONFIG, "mirror_directory": str(mirror)}
    assert client.put("/api/backups/config", json=config, headers=admin[1]).status_code == 200
    disk(monkeypatch, total_gb=32, free_gb=10, only=mirror)  # só o outro disco está cheio
    made = backup(client, admin)
    assert made["mirror"]["status"] == "failed" and "Espaço insuficiente" in made["mirror"]["error"]
    assert not list(mirror.glob("*.zip"))
    disk(monkeypatch, total_gb=32, free_gb=10)  # agora a pasta de backups também
    response = client.post(
        "/api/backups/import",
        files={"file": ("copia.zip", io.BytesIO(content), "application/zip")},
        headers={k: v for k, v in admin[1].items() if k != "Content-Type"},
    )
    assert response.status_code == 507 and "Nada foi copiado" in response.json()["detail"]
    assert not [p for p in directory.iterdir() if p.name.startswith(".import-")]


def test_space_refusals_are_retried_hourly_and_limits_are_validated(client, admin, monkeypatch):
    switch(client, admin)
    assert client.put("/api/backups/config", json=CONFIG, headers=admin[1]).status_code == 200
    for bad in ({"max_total_gb": 0}, {"min_free_percent": 95}, {"min_free_gb": -1}):
        response = client.put("/api/backups/config", json={**CONFIG, **bad}, headers=admin[1])
        assert response.status_code == 422
    disk(monkeypatch, total_gb=64, free_gb=5)
    scheduler = BackupScheduler(manager(client))
    now = datetime.now(BUSINESS_TZ)
    with pytest.raises(Exception) as refused:
        scheduler.tick(now)
    assert refused.value.status_code == 507 and scheduler.backoff == 60
    assert scheduler.tick(now + timedelta(minutes=30)) is None  # não tenta de novo antes de 1 h
    runs = len(manager(client).history()["runs"])
    disk(monkeypatch, total_gb=1000, free_gb=900)
    assert scheduler.tick(now + timedelta(minutes=61))["kind"] == "auto"
    assert len(manager(client).history()["runs"]) == runs + 1
