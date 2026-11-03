"""Real browser/API tests with isolated SQLite and fixture identities only."""

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from alembic import command
from alembic.config import Config
from app.auth.cli import run_local
from app.core.config import Settings
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def own_address():
    """Address another computer of the network would use; None when only loopback exists."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("10.255.255.255", 1))
            address = probe.getsockname()[0]
        except OSError:
            return None
    return None if address.startswith("127.") else address


def relaxed_backup_limits(url):
    """Temporary E2E databases only: the machine running the suite may not have the default
    free-space reserve (10 GB + operational margin, P1-E); the limits are tested in pytest."""
    path = url.removeprefix("sqlite:///")
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES ('backup', ?, 0)",
            (
                json.dumps(
                    {
                        "enabled": False,
                        "frequency": "20min",
                        "time": "22:00",
                        "keep": 14,
                        "directory": "",
                        "mirror_directory": "",
                        "max_total_gb": 10,
                        "min_free_gb": 1,
                        "margin_percent": 0,
                        "margin_max_gb": 0,
                    }
                ),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def station_spki(certificate: Path) -> str:
    """Base64 SHA-256 of the server key: the station browser trusts exactly that key, instead of
    ignoring certificate errors (Chromium --ignore-certificate-errors-spki-list)."""
    import base64
    import hashlib

    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    leaf = x509.load_pem_x509_certificates(certificate.read_bytes())[0]
    spki = leaf.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return base64.b64encode(hashlib.sha256(spki).digest()).decode()


def run_suite(
    env,
    folder,
    base_url,
    port,
    config_name,
    arguments,
    log_name,
    host="127.0.0.1",
    command_line=None,
    ready=None,
):
    """Start a server on the temporary database and run one Playwright configuration."""
    node = shutil.which("node")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (Path(folder) / log_name).open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            command_line
            or [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                host,
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=log,
            creationflags=flags,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Servidor E2E encerrou antes da inicialização")
                try:
                    with urlopen(base_url + "/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Timeout do servidor E2E")
            if ready:
                env = {**env, **ready()}
            result = subprocess.run(
                [
                    node,
                    str(ROOT / "frontend/node_modules/playwright/cli.js"),
                    "test",
                    "--config=" + config_name,
                    *arguments,
                ],
                cwd=ROOT / "frontend",
                env=env,
                creationflags=flags,
                timeout=1500,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            print(result.stdout, flush=True)
            print(result.stderr, file=sys.stderr, flush=True)
        finally:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(server.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                    timeout=15,
                    creationflags=flags,
                )
            else:
                server.terminate()
            server.wait(timeout=15)
    return result


def main():
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js não encontrado")
    temp_root = ROOT / ".test-tmp"
    temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="auth-e2e-", dir=temp_root) as folder:
        url = f"sqlite:///{(Path(folder) / 'identity.db').as_posix()}"
        config = Config(str(ROOT / "backend/alembic.ini"))
        config.attributes["database_url"] = url
        command.upgrade(config, "head")
        relaxed_backup_limits(url)
        settings = Settings(_env_file=None, database_url=url)
        run_local(
            "bootstrap",
            "browser_admin",
            "Administrador E2E",
            "Fixture-browser-password!",
            settings,
        )
        port = free_port()
        base_url = f"http://127.0.0.1:{port}"
        env = {
            **os.environ,
            "LOCACONTROL_DATABASE_URL": url,
            "LOCACONTROL_ALLOWED_ORIGINS": f'["{base_url}"]',
            "LOCACONTROL_COOKIE_SECURE": "false",
            "E2E_AUTH_BASE_URL": base_url,
        }
        fixture = Path(folder) / "customer-workbook.xlsx"
        for index, name in enumerate(
            ("desktop", "full-hd", "tablet", "mobile"), start=1
        ):
            book = Workbook()
            sheet = book.active
            sheet.title = "Dados da empresa"
            sheet.append(
                ["Tipo livre", "Cliente da empresa", "Documento legado", "Não mapeado"]
            )
            sheet.append(
                [
                    "PF",
                    "Cliente importado " + name,
                    "1111111111" + str(index),
                    "Original preservado",
                ]
            )
            sheet.append(["PF", "Cliente inválido", "", "Corrigir documento"])
            book.save(fixture.with_name(fixture.stem + "-" + name + ".xlsx"))
        env["E2E_EXCEL_FILE"] = str(fixture)
        env["LOCACONTROL_IMPORT_DIRECTORY"] = str(Path(folder) / "imports")
        # Generated contract PDFs stay in the temporary folder, never in data/documents.
        env["LOCACONTROL_DOCUMENT_DIRECTORY"] = str(Path(folder) / "documents")
        # Fiscal files and backup sets are temporary too; no scheduled backup during the run.
        env["LOCACONTROL_FISCAL_DIRECTORY"] = str(Path(folder) / "fiscal")
        env["LOCACONTROL_BACKUP_DIRECTORY"] = str(Path(folder) / "backups")
        env["LOCACONTROL_BACKUP_SCHEDULER"] = "false"
        env["LOCACONTROL_FISCAL_PROVIDER"] = "fake"
        result = run_suite(
            env,
            folder,
            base_url,
            port,
            "playwright.auth.config.ts",
            sys.argv[1:],
            "server.log",
        )
        if result.returncode:
            raise SystemExit(result.returncode)
        # Local edition (ADR-023): another server, another empty database, no user at all.
        local_url = f"sqlite:///{(Path(folder) / 'local.db').as_posix()}"
        config.attributes["database_url"] = local_url
        command.upgrade(config, "head")
        relaxed_backup_limits(local_url)
        local_port = free_port()
        local_base = f"http://127.0.0.1:{local_port}"
        local_env = {
            **env,
            "LOCACONTROL_LOCAL_MODE": "true",
            "LOCACONTROL_DATABASE_URL": local_url,
            "LOCACONTROL_ALLOWED_ORIGINS": f'["{local_base}"]',
            "LOCACONTROL_BACKUP_DIRECTORY": str(Path(folder) / "local-backups"),
            "LOCACONTROL_DOCUMENT_DIRECTORY": str(Path(folder) / "local-documents"),
            "E2E_LOCAL_BASE_URL": local_base,
        }
        result = run_suite(
            local_env,
            folder,
            local_base,
            local_port,
            "playwright.local.config.ts",
            [],
            "server-local.log",
        )
        if result.returncode:
            raise SystemExit(result.returncode)
        # Network edition (ADR-025): the main computer and a station at another address.
        address = own_address()
        if address is None:
            print(
                "AVISO: sem endereço de rede não loopback; suíte de rede não executada."
            )
        else:
            # The real entry point (app.server): HTTP on 127.0.0.1 for the main computer and
            # HTTPS on the network for the station, with the local CA (P1-E).
            data = Path(folder) / "rede"
            data.mkdir()
            network_url = f"sqlite:///{(data / 'locacontrol.db').as_posix()}"
            config.attributes["database_url"] = network_url
            command.upgrade(config, "head")
            relaxed_backup_limits(network_url)
            network_port, https_port = free_port(), free_port()
            network_base = f"http://127.0.0.1:{network_port}"
            network_env = {
                key: value
                for key, value in local_env.items()
                if not key.endswith(("_DIRECTORY", "_DATABASE_URL"))
            }
            network_env |= {
                "LOCACONTROL_DATA_DIR": str(data),
                "LOCACONTROL_NETWORK_MODE": "true",
                "LOCACONTROL_STATION_NETWORKS": f'["{address}/32"]',
                "LOCACONTROL_ALLOWED_ORIGINS": f'["{network_base}"]',
                "LOCACONTROL_BACKUP_SCHEDULER": "false",
                "E2E_NETWORK_BASE_URL": network_base,
                "E2E_STATION_BASE_URL": f"https://{address}:{https_port}",
            }

            def https_ready():
                for _ in range(100):
                    try:
                        with socket.create_connection((address, https_port), timeout=1):
                            break
                    except OSError:
                        time.sleep(0.1)
                return {"E2E_STATION_SPKI": station_spki(data / "tls" / "server.pem")}

            result = run_suite(
                network_env,
                folder,
                network_base,
                network_port,
                "playwright.network.config.ts",
                [],
                "server-network.log",
                command_line=[
                    sys.executable,
                    "-m",
                    "app.server",
                    "--port",
                    str(network_port),
                    "--https-port",
                    str(https_port),
                ],
                ready=https_ready,
            )
            if result.returncode:
                raise SystemExit(result.returncode)
    print(
        "PASS: browser/API auth suite, local edition suite and network suite completed;"
        " temporary databases/servers removed"
    )


if __name__ == "__main__":
    main()
