"""Smoke HTTP real: processos isolados, SQLite temporário e limpeza no final."""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def fetch(url):
    # Evita que configurações de proxy corporativo capturem os testes de loopback.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=3) as response:
        return response.status, response.read().decode("utf-8")


def wait_ready(url, process):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Process exited before readiness: {url}")
        try:
            return fetch(url)
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(0.2)
    raise RuntimeError(f"Readiness timeout: {url}")


def main():
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js must be available on PATH")
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise RuntimeError("Run npm --prefix frontend run build before the smoke test")
    backend_port = free_port()
    frontend_port = free_port()
    while frontend_port == backend_port:
        frontend_port = free_port()
    processes = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    temp_root = ROOT / ".test-tmp"
    temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="locacontrol-smoke-", dir=temp_root
    ) as temp:
        temp_path = Path(temp)
        env = os.environ.copy()
        env["LOCACONTROL_DATABASE_URL"] = (
            f"sqlite:///{(temp_path / 'smoke.db').as_posix()}"
        )
        env["LOCACONTROL_PROXY_TARGET"] = f"http://127.0.0.1:{backend_port}"
        log_path = temp_path / "processes.log"
        with log_path.open("w", encoding="utf-8") as log:
            try:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "alembic",
                        "-c",
                        "backend/alembic.ini",
                        "upgrade",
                        "head",
                    ],
                    cwd=ROOT,
                    env=env,
                    check=True,
                    timeout=30,
                    creationflags=flags,
                )
                backend = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--app-dir",
                        "backend",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(backend_port),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=log,
                    stderr=log,
                    creationflags=flags,
                )
                processes.append(backend)
                status, body = wait_ready(
                    f"http://127.0.0.1:{backend_port}/health", backend
                )
                health = json.loads(body)
                assert status == 200 and health["status"] == "ok"
                assert health["database"] == "ok" and health["schema"] == "ok"
                status, html = fetch(f"http://127.0.0.1:{backend_port}/")
                assert status == 200 and 'id="root"' in html
                print(
                    "PASS: backend health, database revision and production HTML",
                    flush=True,
                )

                frontend = subprocess.Popen(
                    [
                        node,
                        str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
                        "preview",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(frontend_port),
                        "--configLoader",
                        "runner",
                    ],
                    cwd=ROOT / "frontend",
                    env=env,
                    stdout=log,
                    stderr=log,
                    creationflags=flags,
                )
                processes.append(frontend)
                status, html = wait_ready(
                    f"http://127.0.0.1:{frontend_port}/", frontend
                )
                assert status == 200 and 'id="root"' in html
                status, proxy_body = fetch(f"http://127.0.0.1:{frontend_port}/health")
                assert status == 200 and json.loads(proxy_body) == health
                print("PASS: Vite HTML and real frontend-to-backend proxy", flush=True)
            except Exception:
                log.flush()
                print(log_path.read_text(encoding="utf-8"), file=sys.stderr)
                raise
            finally:
                for process in reversed(processes):
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            capture_output=True,
                            check=False,
                            timeout=15,
                            creationflags=flags,
                        )
                    else:
                        process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
    print("PASS: isolated smoke finished; temporary processes and database removed")


if __name__ == "__main__":
    main()
