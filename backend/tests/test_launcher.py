"""LocaControl.exe (P1-E): verbos do executável, com o servidor de verdade num processo à parte
(abrir sobe o servidor e ele responde; parar encerra), e as escolhas sem processo."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app import launcher
from app.core.config import PROJECT_ROOT


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    path = tmp_path / "Dados LocaControl"
    path.mkdir()
    monkeypatch.setenv("LOCACONTROL_DATA_DIR", str(path))
    monkeypatch.setenv("LOCACONTROL_LOCAL_MODE", "true")
    monkeypatch.setenv("LOCACONTROL_BACKUP_SCHEDULER", "false")
    for name in ("DATABASE_URL", "BACKUP_DIRECTORY", "NETWORK_MODE"):
        monkeypatch.delenv(f"LOCACONTROL_{name}", raising=False)
    monkeypatch.setenv("PYTHONPATH", str(PROJECT_ROOT / "backend"))
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(key, raising=False)
    return path


def test_open_starts_the_server_once_and_stop_ends_it(data_dir, monkeypatch):
    port = free_port()
    opened = []
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
    assert launcher.main(["abrir", "--porta", str(port)]) == 0
    try:
        assert launcher.health(port)
        assert opened == [f"http://127.0.0.1:{port}/"]
        pid = int((data_dir / "locacontrol.pid").read_text())
        # Abrir de novo não sobe outro servidor: só abre o navegador.
        assert launcher.main(["abrir", "--porta", str(port)]) == 0
        assert int((data_dir / "locacontrol.pid").read_text()) == pid
        assert len(opened) == 2
    finally:
        assert launcher.main(["parar"]) == 0
    deadline = time.monotonic() + 15
    while launcher.health(port) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert not launcher.health(port)
    assert not (data_dir / "locacontrol.pid").exists()
    assert (data_dir / "locacontrol.db").is_file()  # os dados ficam


def test_windowed_server_writes_its_messages_to_the_log(data_dir):
    port = free_port()
    code = (
        "import sys; sys.stdout = None; sys.stderr = None\n"
        "from app import launcher\n"
        f"raise SystemExit(launcher.main(['servir', '--port', '{port}', '--prepare']))\n"
    )
    finished = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, timeout=120)
    assert finished.returncode == 0
    log = (data_dir / "logs" / "servidor.log").read_text(encoding="utf-8")
    assert "Aplicando atualizações do banco" in log


def test_windowed_connect_failure_is_kept_in_the_commands_log(data_dir, monkeypatch):
    """Sem console, o erro do "Conectar à loja" vai para logs/comandos.log (o instalador aponta)."""
    from app.network import connect

    def refuse(*_args, **_kwargs):
        raise connect.ConnectError("A identidade do computador principal NÃO confere")

    monkeypatch.setattr(connect, "connect", refuse)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    code = launcher.main(["conectar", "--servidor", "192.168.0.10", "--codigo", "X"])
    sys.stderr.close()
    assert code == launcher.EXIT_CONNECT_FAILED
    log = (data_dir / "logs" / launcher.COMMANDS_LOG).read_text(encoding="utf-8")
    assert "conectar: A identidade do computador principal NÃO confere" in log


def test_a_station_opens_the_store_address(data_dir, monkeypatch):
    (data_dir / "station.json").write_text(
        json.dumps({"url": "https://192.168.0.10:8443/"}), encoding="utf-8"
    )
    opened, spawned = [], []
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
    monkeypatch.setattr(launcher, "spawn", spawned.append)
    assert launcher.main([]) == 0  # "abrir" é o padrão
    assert opened == ["https://192.168.0.10:8443/"] and spawned == []


def test_connect_failure_returns_its_own_exit_code(data_dir, monkeypatch, capsys):
    from app.network import connect

    def refuse(*_args, **_kwargs):
        raise connect.ConnectError("A identidade do computador principal NÃO confere")

    monkeypatch.setattr(connect, "connect", refuse)
    code = launcher.main(["conectar", "--servidor", "192.168.0.10", "--codigo", "X"])
    assert code == launcher.EXIT_CONNECT_FAILED
    assert "NÃO confere" in capsys.readouterr().err
    assert launcher.main(["inexistente"]) == 64


def test_stop_without_a_running_server_is_harmless(data_dir):
    assert launcher.main(["parar"]) == 0
    # PID deixado por um fim anormal: nada roda (a trava está livre), nada é encerrado, e o
    # arquivo fica para o próximo início verificar o banco (REL-P1E-02).
    (data_dir / "locacontrol.pid").write_text("999999999")
    assert launcher.main(["parar"]) == 0
    assert (data_dir / "locacontrol.pid").exists()


@pytest.mark.skipif(os.name == "nt", reason="caminhos POSIX")
def test_server_command_in_development_and_frozen(monkeypatch):
    assert launcher.server_command(8000)[1:3] == ["-m", "app.launcher"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert launcher.server_command(8001) == [sys.executable, "servir", "--port", "8001"]
    assert Path(launcher.__file__).name == "launcher.py"
