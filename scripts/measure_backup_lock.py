"""M1: latência das gravações enquanto o backup copia o banco (journal_mode=delete, timeout 5 s).

Para cada tamanho (MB) cria um banco temporário, mede a cópia SQLite sozinha e depois um backup
completo com gravações contínuas em paralelo, informando a pior espera e as falhas. Só usa
pastas temporárias em .test-tmp. Uso, na raiz:

    PYTHONPATH=backend python scripts/measure_backup_lock.py 100 400 1000
"""

import shutil
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import PROJECT_ROOT, Settings
from app.main import create_app
from app.ops.backup import BackupManager
from fastapi.testclient import TestClient

APP = {"X-LocaControl-Request": "1"}
RELAXED = {
    "directory": "",
    "keep": 14,
    "mirror_directory": "",
    "max_total_gb": 100,
    "min_free_gb": 1,
    "margin_percent": 0,
    "margin_max_gb": 0,
}


def run(size_mb: int, base: Path):
    root = base / f"m{size_mb}"
    root.mkdir()
    url = f"sqlite:///{(root / 'locacontrol.db').as_posix()}"
    cfg = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "head")
    c = sqlite3.connect(root / "locacontrol.db")
    c.execute("CREATE TABLE lastro (x BLOB)")
    blob = b"\1" * (1 << 20)
    for _ in range(size_mb):
        c.execute("INSERT INTO lastro VALUES (?)", (blob,))
    c.commit()
    c.close()
    settings = Settings(
        _env_file=None,
        local_mode=True,
        database_url=url,
        document_directory=root / "documents",
        fiscal_directory=root / "fiscal",
        import_directory=root / "imports",
        backup_directory=root / "backups",
        backup_scheduler=False,
    )
    app = create_app(settings)
    with TestClient(
        app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 1)
    ) as p:
        csrf = p.get("/api/auth/me", headers=APP).json()["csrf_token"]
        p.headers.update(
            {"Origin": "http://127.0.0.1:8000", **APP, "X-CSRF-Token": csrf}
        )
        # Só a cópia SQLite (sem zip): o tempo em que a leitura fica presa.
        src = sqlite3.connect((root / "locacontrol.db").as_uri() + "?mode=ro", uri=True)
        dst = sqlite3.connect(root / "copia.db")
        t = time.monotonic()
        src.backup(dst)
        copy_s = time.monotonic() - t
        src.close()
        dst.close()
        (root / "copia.db").unlink()
        done, lat, fails = threading.Event(), [], []

        def writer():
            n = 0
            while not done.is_set():
                t0 = time.monotonic()
                r = p.put("/api/drafts/quote/new", json={"payload": {"n": n}})
                lat.append(time.monotonic() - t0)
                if r.status_code != 200:
                    fails.append(r.status_code)
                n += 1

        th = threading.Thread(target=writer)
        th.start()
        t = time.monotonic()
        BackupManager(settings, app.state.engine).create(
            {**RELAXED, "enabled": False}, "manual"
        )
        took = time.monotonic() - t
        done.set()
        th.join()
    shutil.rmtree(root, ignore_errors=True)
    print(
        f"RESULTADO M1 {size_mb} MB: copia_sqlite={copy_s:.2f}s backup_total={took:.2f}s "
        f"gravacoes={len(lat)} pior_espera={max(lat):.2f}s falhas={fails[:3]}",
        flush=True,
    )


def main():
    base = Path(tempfile.mkdtemp(dir=PROJECT_ROOT / ".test-tmp"))
    try:
        for size in [int(a) for a in sys.argv[1:]] or [100, 400, 1000]:
            run(size, base)
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
