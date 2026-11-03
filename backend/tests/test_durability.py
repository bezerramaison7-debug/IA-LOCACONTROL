# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
"""Durabilidade e verificação dos backups (M2): fsync antes de renomear, conjunto relido e
verificado antes de contar como backup, e nada antigo apagado por causa de um conjunto ruim."""

from datetime import datetime, timedelta
from pathlib import Path

from test_backups import backup, manager
from test_quotes import admin, switch  # noqa: F401

from app.core import durable
from app.core.clock import BUSINESS_TZ
from app.ops.backup import BackupManager

CONFIG = {
    "enabled": True,
    "frequency": "20min",
    "time": "22:00",
    "keep": 1,
    "directory": "",
    "mirror_directory": "",
    "max_total_gb": 10,
    "min_free_gb": 10,
    "margin_percent": 5,
    "margin_max_gb": 20,
}


def test_set_and_history_are_flushed_to_disk_before_the_rename(client, admin, monkeypatch):
    flushed = []
    real = durable.os.fsync
    monkeypatch.setattr(durable.os, "fsync", lambda fd: (flushed.append(fd), real(fd)))
    made = backup(client, admin)
    # zip + pasta, histórico + pasta (a pasta não é aberta no Windows).
    assert len(flushed) >= (4 if durable.os.name != "nt" else 2)
    directory = Path(client.app.state.settings.backup_directory)
    assert (directory / made["name"]).is_file()
    assert not list(directory.glob(".*.part"))
    target = directory.parent / "teste.json"
    durable.write_durably(target, b'{"ok": true}')
    assert target.read_bytes() == b'{"ok": true}' and not list(directory.parent.glob(".teste*"))


def test_a_set_that_fails_verification_after_writing_is_set_aside_and_nothing_is_pruned(
    client, admin, monkeypatch
):
    directory = Path(client.app.state.settings.backup_directory)
    directory.mkdir(parents=True)
    old = datetime.now(BUSINESS_TZ) - timedelta(days=5)
    olds = [f"locacontrol_{old + timedelta(days=d):%Y-%m-%d_%H%M%S}.zip" for d in range(3)]
    for name in olds:
        (directory / name).write_bytes(b"conjunto antigo")
    switch(client, admin)
    assert client.put("/api/backups/config", json=CONFIG, headers=admin[1]).status_code == 200
    real = BackupManager.verify

    def broken(self, path):
        report = real(self, path)
        if not path.name.startswith(".") and path.name not in olds:
            return {**report, "ok": False, "errors": ["Conteúdo alterado: locacontrol.db"]}
        return report

    monkeypatch.setattr(BackupManager, "verify", broken)
    response = client.post("/api/backups", headers=admin[1])
    assert response.status_code == 500
    assert "reprovado na verificação" in response.json()["detail"]
    assert "Nenhuma cópia anterior foi apagada" in response.json()["detail"]
    # A retenção (keep=1) teria apagado as antigas; com o novo reprovado, todas continuam.
    listed = [item["name"] for item in manager(client).listing(CONFIG)]
    assert sorted(listed) == sorted(olds)
    assert len(list(directory.glob(".*.reprovado"))) == 1
    history = manager(client).history()
    assert history["runs"][0]["status"] == "failed"
    assert client.get("/api/backups/status").json()["alert"]["level"] == "danger"
    monkeypatch.setattr(BackupManager, "verify", real)
    made = backup(client, admin)  # um conjunto bom depois: aí sim a retenção roda
    assert [item["name"] for item in manager(client).listing(CONFIG)] == [made["name"]]


def test_second_copy_is_verified_from_the_other_folder(client, admin, monkeypatch, tmp_path):
    mirror = tmp_path / "outro-disco"
    switch(client, admin)
    config = {**CONFIG, "keep": 14, "mirror_directory": str(mirror)}
    assert client.put("/api/backups/config", json=config, headers=admin[1]).status_code == 200
    real = BackupManager.verify

    def broken_in_mirror(self, path):
        report = real(self, path)
        if Path(path).parent == mirror:
            return {**report, "ok": False, "errors": ["Arquivo de backup inválido ou ilegível."]}
        return report

    monkeypatch.setattr(BackupManager, "verify", broken_in_mirror)
    made = backup(client, admin)
    assert made["mirror"]["status"] == "failed" and "reprovada" in made["mirror"]["error"]
    assert not list(mirror.glob("locacontrol_*.zip")) and list(mirror.glob(".*.reprovado"))
    assert (Path(client.app.state.settings.backup_directory) / made["name"]).is_file()
