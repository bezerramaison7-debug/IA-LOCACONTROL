"""Single entry point of the LocaControl server (`python -m app.server`, or the packaged exe).

Order: data folder (created only on a first installation) -> exclusive installation lock ->
missing-database check -> schema upgrade with a prior database copy -> first-access account
(login edition only) -> uvicorn on 127.0.0.1 (all interfaces only in the network mode, ADR-025).
A second instance over the same data folder exits with EXIT_ALREADY_RUNNING before touching the
database; an unavailable data folder or a vanished database exits with EXIT_DATA_UNAVAILABLE.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.core.config import Settings, data_root, resource
from app.persistence.database import build_engine, resolve_database_url

EXIT_ALREADY_RUNNING = 3
EXIT_DATA_UNAVAILABLE = 4
# Not enough room for the copy taken before a schema upgrade: nothing was migrated (P1-E).
EXIT_NO_SPACE = 5
# Copies taken before schema upgrades kept per folder; older ones are removed after a new one.
PRE_UPGRADE_KEPT = 3
LOCK_FILE = "locacontrol.lock"
# Written after the first successful preparation: from then on a missing database is an error.
MARKER = "locacontrol.installed"


class AlreadyRunning(RuntimeError):
    pass


class DataUnavailable(RuntimeError):
    pass


class NoSpace(RuntimeError):
    pass


def ensure_data_dir(root: Path):
    """Creates the data folder only on a first installation: its parent must already exist.

    A missing parent means an absent drive or network share, never a reason to start empty.
    """
    if root.is_dir():
        return
    if root.exists():
        raise DataUnavailable(f"O caminho de dados {root} existe, mas não é uma pasta.")
    if not root.parent.is_dir():
        raise DataUnavailable(
            f"A pasta de dados {root} está indisponível (unidade ou pasta {root.parent} "
            "não encontrada). Conecte a unidade ou corrija LOCACONTROL_DATA_DIR."
        )
    try:
        root.mkdir()
    except OSError as error:
        raise DataUnavailable(f"Sem permissão para criar a pasta de dados {root}.") from error


def check_database(settings: Settings, root: Path):
    """Refuses to create an empty database where one existed or its folder is missing."""
    database = database_file(settings)
    if database is None or database.is_file():
        return
    if not database.parent.is_dir():
        raise DataUnavailable(f"A pasta do banco {database.parent} está indisponível.")
    if (root / MARKER).exists():
        raise DataUnavailable(
            f"O banco {database} não foi encontrado, mas esta pasta de dados já foi usada. "
            "Nada foi criado. Restaure um backup ou corrija o caminho configurado."
        )


def acquire_lock(directory: Path):
    """OS lock on one byte of the lock file; the OS drops it when the process ends, even killed.

    Keep the returned handle open for the life of the process; closing it releases the lock.
    """
    handle = open(directory / LOCK_FILE, "a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        handle.close()
        raise AlreadyRunning(
            f"O LocaControl já está em execução com os dados de {directory}. "
            "Use a janela aberta ou encerre-o antes de iniciar outra vez."
        ) from error
    return handle


def database_file(settings: Settings) -> Path | None:
    url = resolve_database_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
        return None
    return Path(url.database)


def copy_database(source: Path, directory: Path) -> Path:
    """Consistent online copy (SQLite backup API), refused unless it passes integrity_check."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"pre-upgrade-{datetime.now():%Y%m%d-%H%M%S}.db"
    origin, copy = sqlite3.connect(source), sqlite3.connect(target)
    try:
        origin.backup(copy)
        ok = copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        copy.close()
        origin.close()
    if not ok:
        raise RuntimeError(f"A cópia prévia {target} falhou na verificação; nada foi migrado.")
    return target


def saved_limits(database: Path) -> dict:
    """Backup limits saved in the database itself, read without the ORM (old schemas too)."""
    try:
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        try:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = 'backup'"
            ).fetchone()
        finally:
            connection.close()
        return json.loads(row[0]) if row else {}
    except (sqlite3.Error, ValueError, TypeError):
        return {}


def copy_folder(settings: Settings, database: Path) -> Path:
    """Where the pre-upgrade copy fits keeping the free-space reserve: the backup folder, else
    the data folder. Neither: NoSpace, and the upgrade does not run (the database is untouched)."""
    from app.ops.backup import BackupManager
    from app.ops.storage import reserve_bytes

    size = database.stat().st_size
    limits = saved_limits(database)
    for folder in (Path(settings.backup_directory), database.parent):
        anchor = next((p for p in (folder, *folder.parents) if p.exists()), None)
        if anchor is None:
            continue
        usage = BackupManager.disk_usage(anchor)
        if usage.free - size >= reserve_bytes(usage.total, limits, size):
            return folder
    raise NoSpace(
        "Espaço insuficiente para a cópia de segurança do banco antes da atualização "
        f"(o banco tem {size / 1024**2:.0f} MB e o disco precisa manter o espaço mínimo livre). "
        "Nada foi alterado: libere espaço no disco e inicie o LocaControl de novo."
    )


def prune_pre_upgrade(folder: Path, keep: int = PRE_UPGRADE_KEPT):
    copies = sorted(folder.glob("pre-upgrade-*.db"), key=lambda p: p.name, reverse=True)
    for old in copies[keep:]:
        old.unlink(missing_ok=True)


def migrate(settings: Settings) -> Path | None:
    """Upgrades to head; an existing database is copied first. Returns the copy, if any."""
    config = Config(str(resource("backend/alembic.ini")))
    config.attributes["database_url"] = settings.database_url
    expected = set(ScriptDirectory.from_config(config).get_heads())
    engine = build_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            current = set(MigrationContext.configure(connection).get_current_heads())
    finally:
        engine.dispose()
    if current == expected:
        return None
    copy = None
    database = database_file(settings)
    if database and database.is_file() and database.stat().st_size:
        folder = copy_folder(settings, database)
        copy = copy_database(database, folder)
        prune_pre_upgrade(folder)
        print(f"Cópia do banco antes da atualização: {copy}", flush=True)
    print("Aplicando atualizações do banco de dados...", flush=True)
    command.upgrade(config, "head")
    return copy


def prepare(settings: Settings) -> bool:
    """Schema and first-access account. True when the admin/admin account was created."""
    migrate(settings)
    if settings.local_mode:
        return False  # local edition (ADR-023): no login, no admin/admin
    from app.auth.cli import create_default

    created = create_default(settings)
    if created:
        print('PRIMEIRO ACESSO: usuário "admin" e senha "admin".', flush=True)
        print("O sistema exigirá uma nova senha (12 caracteres ou mais).", flush=True)
    return created


def listen_address(settings: Settings) -> str:
    """The store network only when the network mode was chosen (local edition, ADR-025)."""
    if settings.local_mode and settings.network_mode:
        return "0.0.0.0"
    if settings.network_mode:
        print("LOCACONTROL_NETWORK_MODE exige LOCACONTROL_LOCAL_MODE; ignorado.", flush=True)
    return "127.0.0.1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Servidor do LocaControl")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--prepare", action="store_true", help="só prepara o banco e encerra, sem servir"
    )
    args = parser.parse_args(argv)
    root = data_root()
    try:
        ensure_data_dir(root)
        lock = acquire_lock(root)
    except DataUnavailable as error:
        print(error, file=sys.stderr, flush=True)
        return EXIT_DATA_UNAVAILABLE
    except AlreadyRunning as error:
        print(error, file=sys.stderr, flush=True)
        return EXIT_ALREADY_RUNNING
    try:
        settings = Settings()
        try:
            check_database(settings, root)
        except DataUnavailable as error:
            print(error, file=sys.stderr, flush=True)
            return EXIT_DATA_UNAVAILABLE
        try:
            prepare(settings)
        except NoSpace as error:
            print(error, file=sys.stderr, flush=True)
            return EXIT_NO_SPACE
        (root / MARKER).touch()
        if args.prepare:
            return 0
        own = [f"http://127.0.0.1:{args.port}", f"http://localhost:{args.port}"]
        settings.allowed_origins += [o for o in own if o not in settings.allowed_origins]
        host = listen_address(settings)
        if host != "127.0.0.1":
            print(
                f"Modo rede: estações pareadas acessam este computador na porta {args.port}.",
                flush=True,
            )
        import uvicorn

        from app.main import create_app

        uvicorn.run(create_app(settings), host=host, port=args.port)
        return 0
    finally:
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
