"""Encerramento controlado e recuperação (REL-P1E-02, revisão do PR #8).

- atualização do banco interrompida à força (processo morto no meio de uma migration): o banco
  volta ao estado de antes e a atualização é refeita, sem perda;
- recuperação pela cópia prévia mesmo se a migration não tivesse sido atômica;
- sem cópia utilizável e banco em estado desconhecido: nada é alterado e o início é recusado;
- fim anormal (arquivo de PID deixado para trás): integrity_check antes de servir; banco danificado
  impede o início; arquivos de backup incompletos são removidos;
- `parar` pede o encerramento e espera o backup em andamento terminar; com --sem-forcar não força;
  forçado, deixa o PID para o próximo início verificar o banco.
"""

import hashlib
import http.cookiejar
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app import launcher, server
from app.core.config import PROJECT_ROOT, resource

HEAD = "0013_audit_station"
OLD = "0011_drafts"
# Morre (como um taskkill /F ou uma queda de energia) no meio da migration 0013.
KILL_IN_MIGRATION = (
    "import os, runpy, sys\n"
    "from sqlalchemy import event\n"
    "from sqlalchemy.engine import Engine\n"
    "@event.listens_for(Engine, 'before_cursor_execute')\n"
    "def boom(conn, cursor, statement, params, context, many):\n"
    "    if 'CREATE INDEX ix_audit_logs_station_id' in statement:\n"
    "        os._exit(9)\n"
    "sys.argv = ['app.server', *sys.argv[1:]]\n"
    "runpy.run_module('app.server', run_name='__main__', alter_sys=True)\n"
)
# Servidor real com backups lentos (LOCACONTROL_TEST_BACKUP_SECONDS), para parar no meio de um.
SLOW_BACKUP = (
    "import os, runpy, sys, time\n"
    "from app.ops import backup\n"
    "original = backup.BackupManager._create\n"
    "def slow(self, config, kind):\n"
    "    time.sleep(float(os.environ['LOCACONTROL_TEST_BACKUP_SECONDS']))\n"
    "    return original(self, config, kind)\n"
    "backup.BackupManager._create = slow\n"
    "sys.argv = ['app.server', *sys.argv[1:]]\n"
    "runpy.run_module('app.server', run_name='__main__', alter_sys=True)\n"
)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    path = tmp_path / "Dados LocaControl"
    path.mkdir()
    monkeypatch.setenv("LOCACONTROL_DATA_DIR", str(path))
    monkeypatch.setenv("LOCACONTROL_LOCAL_MODE", "true")
    monkeypatch.setenv("LOCACONTROL_BACKUP_SCHEDULER", "false")
    for name in ("DATABASE_URL", "BACKUP_DIRECTORY", "NETWORK_MODE"):
        monkeypatch.delenv(f"LOCACONTROL_{name}", raising=False)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(key, raising=False)
    return path


def env(data_dir: Path, **extra) -> dict:
    return {
        **os.environ,
        "PYTHONPATH": str(PROJECT_ROOT / "backend"),
        "LOCACONTROL_DATA_DIR": str(data_dir),
        **extra,
    }


def database(data_dir: Path) -> Path:
    return data_dir / "locacontrol.db"


def upgrade(path: Path, target: str):
    config = Config(str(resource("backend/alembic.ini")))
    config.attributes["database_url"] = f"sqlite:///{path.as_posix()}"
    command.upgrade(config, target)


def old_database_with_data(data_dir: Path) -> Path:
    """Base numa revisão antiga, com um dado comercial de teste e reserva de espaço pequena
    (processos à parte não veem o disco simulado do conftest)."""
    path = database(data_dir)
    upgrade(path, OLD)
    connection = sqlite3.connect(path)
    limits = {"max_total_gb": 10, "min_free_gb": 1, "margin_percent": 0, "margin_max_gb": 0}
    connection.execute(
        "INSERT INTO app_settings (key, value, updated_at) VALUES ('backup', ?, 0)",
        (json.dumps({"enabled": False, **limits}),),
    )
    connection.execute(
        "INSERT INTO app_settings (key, value, updated_at) VALUES ('teste.dado', '\"guardado\"', 0)"
    )
    connection.commit()
    connection.close()
    (data_dir / server.MARKER).touch()
    return path


def revision(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        return connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    finally:
        connection.close()


def columns(path: Path, table: str) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    finally:
        connection.close()


def kept_value(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        return connection.execute(
            "SELECT value FROM app_settings WHERE key = 'teste.dado'"
        ).fetchone()[0]
    finally:
        connection.close()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(data_dir: Path, code: str | None = None) -> subprocess.CompletedProcess:
    arguments = ["-c", code, "--prepare"] if code else ["-m", "app.server", "--prepare"]
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=PROJECT_ROOT,
        env=env(data_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )


# ---- atualização interrompida ---------------------------------------------------------------


def test_a_schema_upgrade_killed_midway_rolls_back_and_is_redone(data_dir):
    path = old_database_with_data(data_dir)
    killed = prepare(data_dir, KILL_IN_MIGRATION)
    assert killed.returncode == 9, killed.stderr
    assert (data_dir / server.UPGRADE_MARKER).exists()
    # Uma transação só (migrations/env.py): nada da atualização ficou pela metade.
    assert revision(path) == OLD and "station_id" not in columns(path, "audit_logs")
    assert "station_id" not in columns(path, "auth_sessions")
    again = prepare(data_dir)
    assert again.returncode == 0, again.stderr
    assert "voltou à cópia feita imediatamente antes" in again.stdout
    assert revision(path) == HEAD and server.integrity(path) == "ok"
    assert kept_value(path) == '"guardado"'
    assert not (data_dir / server.UPGRADE_MARKER).exists()


def test_recovery_uses_the_copy_even_if_a_migration_had_left_the_schema_half_done(data_dir):
    """O modo de falha de antes da correção (DDL fora de transação): revisão antiga com a coluna
    nova já criada, e o reinício parava em "duplicate column". A cópia prévia resolve sozinha."""
    path = old_database_with_data(data_dir)
    copy = server.copy_database(path, data_dir / "backups")
    connection = sqlite3.connect(path)
    connection.execute("ALTER TABLE audit_logs ADD COLUMN station_id VARCHAR(36)")
    connection.commit()
    connection.close()
    (data_dir / server.UPGRADE_MARKER).write_text(
        json.dumps({"copy": str(copy), "new_database": False, "from": [OLD]}), encoding="utf-8"
    )
    result = prepare(data_dir)
    assert result.returncode == 0, result.stderr
    assert revision(path) == HEAD and kept_value(path) == '"guardado"'


def test_without_a_usable_copy_an_unknown_state_is_refused_untouched(data_dir):
    path = old_database_with_data(data_dir)
    connection = sqlite3.connect(path)
    connection.execute("ALTER TABLE audit_logs ADD COLUMN station_id VARCHAR(36)")
    connection.execute("UPDATE alembic_version SET version_num = '0012_stations'")
    connection.commit()
    connection.close()
    (data_dir / server.UPGRADE_MARKER).write_text(
        json.dumps({"copy": str(data_dir / "sumiu.db"), "new_database": False, "from": [OLD]}),
        encoding="utf-8",
    )
    before = digest(path)
    result = prepare(data_dir)
    assert result.returncode == server.EXIT_DATABASE_DAMAGED
    assert "Nada foi alterado" in result.stderr
    assert digest(path) == before and (data_dir / server.UPGRADE_MARKER).exists()


def test_a_failed_migration_is_undone_at_once(data_dir, monkeypatch, capsys):
    path = old_database_with_data(data_dir)
    real = command.upgrade

    def half_then_fail(config, target):
        real(config, "0012_stations")  # parte da atualização gravada...
        raise RuntimeError("migration com defeito (simulado)")

    monkeypatch.setattr(server.command, "upgrade", half_then_fail)
    with pytest.raises(RuntimeError):
        server.main(["--prepare"])
    assert "voltou à cópia" in capsys.readouterr().err
    assert revision(path) == OLD and kept_value(path) == '"guardado"'
    assert not (data_dir / server.UPGRADE_MARKER).exists()


# ---- fim anormal ----------------------------------------------------------------------------


def damage(path: Path):
    """Estraga páginas do meio do arquivo (o cabeçalho fica intacto)."""
    size = path.stat().st_size
    with open(path, "r+b") as handle:
        handle.seek(size // 2)
        handle.write(os.urandom(min(8192, size // 4)))


def test_after_an_unclean_end_the_database_is_checked_before_serving(data_dir, capsys):
    path = old_database_with_data(data_dir)
    assert server.main(["--prepare"]) == 0
    backups = data_dir / "backups"
    backups.mkdir(exist_ok=True)
    partial = backups / ".locacontrol_2026-11-03_120000.zip.part"
    partial.write_bytes(b"incompleto")
    finished = backups / "locacontrol_2026-11-03_110000.zip"
    finished.write_bytes(b"conjunto pronto")
    (data_dir / server.PID_FILE).write_text("4242", encoding="ascii")
    capsys.readouterr()
    assert server.main(["--prepare"]) == 0
    out = capsys.readouterr().out
    assert "não foi encerrado normalmente" in out and "íntegro" in out
    assert not partial.exists() and finished.exists()  # só o incompleto sai
    assert not (data_dir / server.PID_FILE).exists()
    # Banco danificado depois de um fim anormal: nada é servido nem alterado.
    damage(path)
    (data_dir / server.PID_FILE).write_text("4242", encoding="ascii")
    before = digest(path)
    assert server.main(["--prepare"]) == server.EXIT_DATABASE_DAMAGED
    assert "falhou na verificação de integridade" in capsys.readouterr().err
    assert digest(path) == before and (data_dir / server.PID_FILE).exists()


def test_a_normal_start_does_not_pay_for_the_check(data_dir, monkeypatch):
    old_database_with_data(data_dir)
    assert server.main(["--prepare"]) == 0
    monkeypatch.setattr(server, "integrity", lambda *_: pytest.fail("verificação desnecessária"))
    assert server.main(["--prepare"]) == 0


# ---- parar -----------------------------------------------------------------------------------


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class Running:
    """Servidor de verdade num processo à parte, com backups que levam `seconds`."""

    def __init__(self, data_dir: Path, seconds: float):
        old_database_with_data(data_dir)
        assert prepare(data_dir).returncode == 0
        self.data_dir, self.port = data_dir, free_port()
        self.log = (data_dir.parent / "servidor.log").open("w", encoding="utf-8")
        self.process = subprocess.Popen(
            [sys.executable, "-c", SLOW_BACKUP, "--port", str(self.port)],
            cwd=PROJECT_ROOT,
            env=env(data_dir, LOCACONTROL_TEST_BACKUP_SECONDS=str(seconds)),
            stdout=self.log,
            stderr=subprocess.STDOUT,
        )
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar)
        )
        for _ in range(300):
            if launcher.health(self.port, timeout=1):
                break
            assert self.process.poll() is None, self.text()
            time.sleep(0.1)
        me = self.call("GET", "/api/auth/me")
        self.csrf = me["csrf_token"]

    def call(self, method: str, path: str, timeout: float = 120):
        headers = {"X-LocaControl-Request": "1", "Origin": f"http://127.0.0.1:{self.port}"}
        if method != "GET":
            headers["X-CSRF-Token"] = self.csrf
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            method=method,
            headers=headers,
            data=b"" if method != "GET" else None,
        )
        with self.opener.open(request, timeout=timeout) as response:
            return json.loads(response.read())

    def backup_in_background(self) -> dict:
        outcome = {}

        def run():
            try:
                outcome["result"] = self.call("POST", "/api/backups")
            except Exception as error:  # noqa: BLE001 — the assertion reports it
                outcome["error"] = repr(error)

        thread = threading.Thread(target=run)
        thread.start()
        outcome["thread"] = thread
        time.sleep(1.0)  # o backup começou (dorme dentro do servidor)
        return outcome

    def text(self) -> str:
        self.log.flush()
        return (self.data_dir.parent / "servidor.log").read_text(encoding="utf-8")

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=20)
        self.log.close()


@pytest.fixture
def running(data_dir):
    servers = []

    def start(seconds: float) -> Running:
        servers.append(Running(data_dir, seconds))
        return servers[-1]

    yield start
    for item in servers:
        item.close()


def valid_sets(data_dir: Path) -> list[Path]:
    sets = sorted((data_dir / "backups").glob("locacontrol_*.zip"))
    for path in sets:
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
    return sets


def test_stop_waits_for_the_backup_in_progress(running, data_dir):
    server_process = running(4)
    started = time.monotonic()
    backup = server_process.backup_in_background()
    assert launcher.main(["parar", "--espera", "60"]) == 0
    backup["thread"].join(timeout=60)
    assert "error" not in backup, backup.get("error")  # a requisição terminou com resposta
    assert backup["result"]["name"].startswith("locacontrol_")
    assert time.monotonic() - started >= 3  # esperou o backup, não o interrompeu
    assert server_process.process.wait(timeout=30) == 0
    assert len(valid_sets(data_dir)) == 1
    assert "encerrado normalmente" in server_process.text()
    assert not (data_dir / server.PID_FILE).exists()
    assert not list((data_dir / "backups").glob(".locacontrol_*"))


def test_stop_without_force_never_interrupts(running, data_dir):
    server_process = running(6)
    backup = server_process.backup_in_background()
    assert launcher.main(["parar", "--espera", "1", "--sem-forcar"]) == launcher.EXIT_STILL_RUNNING
    assert server_process.process.poll() is None  # continua rodando, nada foi forçado
    backup["thread"].join(timeout=60)
    assert "error" not in backup, backup.get("error")
    assert server_process.process.wait(timeout=30) == 0  # o pedido feito segue valendo
    assert len(valid_sets(data_dir)) == 1


def test_a_forced_stop_is_reported_and_checked_at_the_next_start(running, data_dir):
    server_process = running(30)
    server_process.backup_in_background()
    assert launcher.main(["parar", "--espera", "2"]) == launcher.EXIT_FORCED
    server_process.process.wait(timeout=30)
    assert (data_dir / server.PID_FILE).exists()  # fim anormal fica registrado
    result = prepare(data_dir)
    assert result.returncode == 0, result.stderr
    assert "não foi encerrado normalmente" in result.stdout and "íntegro" in result.stdout
    assert server.integrity(database(data_dir)) == "ok"
    assert not list((data_dir / "backups").glob(".locacontrol_*"))
