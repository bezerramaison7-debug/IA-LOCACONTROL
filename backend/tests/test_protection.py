# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
"""Proteção automática (ADR-024): intervalo de 20/60 minutos, compatibilidade com a configuração
diária anterior, retenção, histórico de sucesso e falha, aviso, segunda cópia, sem sobreposição
e importação de um backup guardado em outro disco."""

import io
import shutil
import threading
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session
from test_backups import backup, document, manager
from test_integrity import relogin, restore
from test_quotes import PASSWORD, admin, base, customer, login, switch  # noqa: F401

from app.contracts.models import AppSetting
from app.core.clock import BUSINESS_TZ
from app.ops.backup import (
    NAME,
    OPERATION_LOCK,
    SETTING_KEY,
    BackupScheduler,
    due,
    moment,
    retained,
)

CONFIG = {
    "enabled": True,
    "frequency": "20min",
    "time": "22:00",
    "keep": 14,
    "directory": "",
    "mirror_directory": "",
}


def configure(client, admin, **values):
    switch(client, admin)
    response = client.put("/api/backups/config", json={**CONFIG, **values}, headers=admin[1])
    assert response.status_code == 200, response.text
    return response.json()


def stamp(when: datetime, suffix: str = "") -> str:
    return f"locacontrol_{when:%Y-%m-%d_%H%M%S}{suffix}.zip"


def test_saved_daily_configuration_keeps_working_and_new_ones_run_every_20_minutes(client, admin):
    backups = manager(client)
    with Session(client.app.state.engine) as db:
        assert backups.config(db)["frequency"] == "20min"
        assert backups.config(db)["enabled"] is True
        # Linha gravada antes da ADR-024: sem "frequency" e sem segunda cópia.
        db.add(
            AppSetting(
                key=SETTING_KEY,
                value={"enabled": True, "time": "21:30", "keep": 7, "directory": ""},
            )
        )
        db.commit()
        legacy = backups.config(db)
    assert legacy["frequency"] == "daily" and legacy["time"] == "21:30" and legacy["keep"] == 7
    assert legacy["mirror_directory"] == ""
    switch(client, admin)
    overview = client.get("/api/backups").json()
    assert overview["config"]["frequency"] == "daily"
    night = datetime(2026, 11, 2, 21, 30, tzinfo=BUSINESS_TZ)
    assert due(legacy, night, []) is True and due(legacy, night - timedelta(minutes=1), []) is False
    bad = client.put("/api/backups/config", json={**CONFIG, "frequency": "5min"}, headers=admin[1])
    assert bad.status_code == 422
    assert configure(client, admin, frequency="60min")["config"]["frequency"] == "60min"


def test_interval_schedule_and_retention_rules():
    now = datetime(2026, 11, 2, 15, 0, tzinfo=BUSINESS_TZ)
    config = {**CONFIG}
    assert due(config, now, []) is True
    assert due(config, now, [stamp(now - timedelta(minutes=19))]) is False
    assert due(config, now, [stamp(now - timedelta(minutes=20))]) is True
    # Um backup manual recente cobre o intervalo; a cópia anterior a uma restauração não.
    assert due(config, now, [stamp(now - timedelta(minutes=5), "_pre-restore")]) is True
    assert due(config, now, [stamp(now - timedelta(minutes=5), "_importado")]) is True
    # "Nada mudou" verificado há 10 minutos também cobre o intervalo.
    old = [stamp(now - timedelta(hours=3))]
    assert due(config, now, old, now - timedelta(minutes=10)) is False
    assert due({**config, "frequency": "60min"}, now, [stamp(now - timedelta(minutes=40))]) is False
    assert due({**config, "enabled": False}, now, []) is False

    names = [stamp(now - timedelta(minutes=20 * n)) for n in range(1, 80)]  # 26 horas
    names += [stamp(now - timedelta(days=d)) for d in range(2, 30)]
    names += [stamp(now - timedelta(days=40), "_pre-restore")]
    kept = retained(names, 14, now)
    recent = [n for n in names[:79] if now - moment(NAME.match(n)) < timedelta(hours=24)]
    assert set(recent) <= kept  # tudo das últimas 24 horas
    days = {n[12:22] for n in kept}
    assert len(days) == 14  # e o mais recente de cada um dos 14 dias mais recentes
    assert stamp(now - timedelta(days=13)) in kept and stamp(now - timedelta(days=14)) not in kept
    assert not any(n.endswith("_pre-restore.zip") for n in kept)  # fora da retenção


def test_scheduler_records_runs_skips_unchanged_data_and_warns_on_failure(client, admin, base):
    person, item = base
    configure(client, admin)
    backups = manager(client)
    scheduler = BackupScheduler(backups)
    now = datetime.now(BUSINESS_TZ)
    first = scheduler.tick(now)
    assert first["kind"] == "auto"
    assert scheduler.tick(now + timedelta(minutes=5)) is None  # dentro do intervalo
    # Nada mudou em 20 minutos: só registra a verificação, sem cópia repetida.
    skipped = scheduler.tick(now + timedelta(minutes=21))
    assert skipped == {"skipped": True, "reason": "unchanged", "last": first["name"]}
    assert len(client.get("/api/backups").json()["items"]) == 1
    status = client.get("/api/backups/status").json()
    assert status["alert"] is None and status["unchanged_at"]
    assert status["last_success"]["name"] == first["name"]
    assert "computador" in status["requires_running"]
    assert scheduler.tick(now + timedelta(minutes=30)) is None

    customer(client, admin, "11144477735")  # dado novo: o próximo intervalo copia
    second = scheduler.tick(now + timedelta(minutes=45))
    assert second and second["kind"] == "auto" and second["name"] != first["name"]

    # Pasta de backups indisponível (um arquivo no lugar da pasta): falha registrada e avisada.
    blocked = Path(client.app.state.settings.backup_directory).parent / "bloqueado"
    blocked.write_text("não é pasta")
    with Session(client.app.state.engine) as db:
        row = db.get(AppSetting, SETTING_KEY)
        row.value = {**row.value, "directory": str(blocked / "sub")}
        db.commit()
    later = now + timedelta(hours=2)
    failed = None
    try:
        scheduler.tick(later)
    except Exception as error:  # noqa: BLE001 — o thread registra e segue
        failed = error
    assert failed is not None
    history = backups.history()
    assert history["runs"][0]["status"] == "failed" and history["runs"][0]["kind"] == "auto"
    assert history["last_failure"]["error"]
    status = client.get("/api/backups/status").json()
    assert status["alert"]["level"] == "danger" and "falhou" in status["alert"]["message"]
    # Depois de uma falha, nova tentativa só depois de alguns minutos, não a cada minuto.
    assert scheduler.tick(later + timedelta(minutes=1)) is None
    assert len(backups.history()["runs"]) == len(history["runs"])

    configure(client, admin)  # pasta corrigida: o backup seguinte limpa o aviso
    switch(client, admin)
    assert client.post("/api/backups", headers=admin[1]).status_code == 201
    assert client.get("/api/backups/status").json()["alert"] is None
    kinds = [run["kind"] for run in backups.history()["runs"]]
    assert kinds[:2] == ["manual", "auto"]


def test_no_overlap_and_disabled_or_stale_backups_are_warned(client, admin):
    configure(client, admin)
    backups = manager(client)
    scheduler = BackupScheduler(backups)
    assert OPERATION_LOCK.acquire(blocking=False)
    try:
        # Outro backup ou uma restauração em andamento: este minuto é pulado, sem fila.
        holder_result = []
        thread = threading.Thread(target=lambda: holder_result.append(scheduler.tick()))
        thread.start()
        thread.join(5)
        assert holder_result == [None]
    finally:
        OPERATION_LOCK.release()
    status = client.get("/api/backups/status").json()
    assert status["alert"]["message"] == "Nenhum backup concluído ainda."
    made = scheduler.tick()
    assert made["kind"] == "auto"
    with Session(client.app.state.engine) as db:
        config = backups.config(db)
    stale = backups.status(config, datetime.now(BUSINESS_TZ) + timedelta(hours=3))
    assert stale["alert"]["level"] == "warning" and "ligados" in stale["alert"]["message"]
    configure(client, admin, enabled=False)
    status = client.get("/api/backups/status").json()
    assert "desativado" in status["alert"]["message"]


def test_second_copy_in_another_folder_and_its_failure(client, admin, base):
    root = Path(client.app.state.settings.backup_directory).parent
    mirror = root / "outro-disco"
    switch(client, admin)
    same = client.put(
        "/api/backups/config",
        json={**CONFIG, "mirror_directory": str(client.app.state.settings.backup_directory)},
        headers=admin[1],
    )
    assert same.status_code == 422
    configure(client, admin, mirror_directory=str(mirror))
    created = backup(client, admin)
    assert created["mirror"]["status"] == "ok"
    original = Path(client.app.state.settings.backup_directory) / created["name"]
    assert (mirror / created["name"]).read_bytes() == original.read_bytes()
    assert manager(client).verify(mirror / created["name"])["ok"]

    # O disco da segunda cópia foi desconectado: o backup principal vale, o aviso aparece.
    shutil.rmtree(mirror)
    mirror.write_text("disco ausente")
    second = backup(client, admin)
    assert second["mirror"]["status"] == "failed"
    status = client.get("/api/backups/status").json()
    assert status["last_success"]["name"] == second["name"]
    assert status["alert"]["level"] == "warning" and "segunda cópia" in status["alert"]["message"]


def test_backup_kept_on_another_disk_is_imported_verified_and_restored(client, admin, base):
    person, item = base
    document(client, admin, person, item)
    created = backup(client, admin)
    directory = Path(client.app.state.settings.backup_directory)
    content = (directory / created["name"]).read_bytes()
    # Simula o pendrive: o conjunto sai da pasta de backups e só existe "em outro disco".
    (directory / created["name"]).unlink()
    customer(client, admin, "11144477735")
    switch(client, admin)

    def upload(data: bytes, filename: str = "copia-do-pendrive.zip"):
        return client.post(
            "/api/backups/import",
            files={"file": (filename, io.BytesIO(data), "application/zip")},
            headers={k: v for k, v in admin[1].items() if k != "Content-Type"},
        )

    assert upload(b"nada", "planilha.xlsx").status_code == 422
    garbage = upload(b"PK\x03\x04 isto nao e um backup")
    assert garbage.status_code == 422 and "Nada foi copiado" in garbage.json()["detail"]
    tampered = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(tampered, "w") as out:
        for member in source.namelist():
            data = source.read(member)
            out.writestr(member, data + b"x" if member.startswith("documents/") else data)
    assert upload(tampered.getvalue()).status_code == 422
    assert not [p for p in directory.iterdir() if p.name.startswith(".import-")]

    imported = upload(content)
    assert imported.status_code == 201, imported.text
    name = imported.json()["name"]
    assert name.endswith("_importado.zip") and imported.json()["ok"] is True
    assert upload(content).status_code == 409  # o mesmo arquivo de novo
    actions = [entry["action"] for entry in client.get("/api/audit-logs").json()["items"]]
    assert "backup.imported" in actions
    listed = {item["name"]: item["kind"] for item in client.get("/api/backups").json()["items"]}
    assert listed[name] == "imported"
    # A retenção nunca apaga um conjunto importado que aguarda restauração.
    manager(client).prune({**CONFIG, "keep": 1})
    assert (directory / name).is_file()

    response = restore(client, admin[1], name)
    assert response.status_code == 200, response.text
    relogin(client)
    assert client.get("/api/customers").json()["total"] == 1
    assert client.get("/api/contracts").json()["total"] == 1
