"""Real browser/API tests with isolated SQLite and fixture identities only."""

import os
import shutil
import socket
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
        settings = Settings(_env_file=None, database_url=url)
        run_local(
            "bootstrap",
            "browser_admin",
            "Administrador E2E",
            "Fixture-browser-password!",
            settings,
        )
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
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
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with (Path(folder) / "server.log").open("w", encoding="utf-8") as log:
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
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
                        raise RuntimeError(
                            "Servidor E2E encerrou antes da inicialização"
                        )
                    try:
                        with urlopen(base_url + "/health", timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Timeout do servidor E2E")
                result = subprocess.run(
                    [
                        node,
                        str(ROOT / "frontend/node_modules/playwright/cli.js"),
                        "test",
                        "--config=playwright.auth.config.ts",
                        *sys.argv[1:],
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
        if result.returncode:
            raise SystemExit(result.returncode)
    print("PASS: browser/API auth suite completed; temporary database/server removed")


if __name__ == "__main__":
    main()
