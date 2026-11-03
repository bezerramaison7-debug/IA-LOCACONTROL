"""Single entry point of the LocaControl server (`python -m app.server`, or the packaged exe).

Order: data folder (created only on a first installation) -> exclusive installation lock ->
missing-database check -> schema upgrade with a prior database copy -> first-access account
(login edition only) -> uvicorn on 127.0.0.1 (all interfaces only in the network mode, ADR-025).
A second instance over the same data folder exits with EXIT_ALREADY_RUNNING before touching the
database; an unavailable data folder or a vanished database exits with EXIT_DATA_UNAVAILABLE.

Controlled shutdown (REL-P1E-02): a stop request (the file STOP_FILE, a Windows service STOP or
SIGTERM) makes the listeners stop accepting, waits for the requests in progress, then the backup
scheduler and any backup or restore, and only then exits. A start after an unclean end (the PID
file was left behind) checks the database with integrity_check before serving; a schema upgrade
that was interrupted is undone from the copy taken right before it.
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.core.config import Settings, data_root, resource
from app.core.durable import fsync_file, write_durably
from app.persistence.database import build_engine, resolve_database_url

EXIT_ALREADY_RUNNING = 3
EXIT_DATA_UNAVAILABLE = 4
# Not enough room for the copy taken before a schema upgrade: nothing was migrated (P1-E).
EXIT_NO_SPACE = 5
# The database failed integrity_check after an unclean end: nothing is served (REL-P1E-02).
EXIT_DATABASE_DAMAGED = 8
# Copies taken before schema upgrades kept per folder; older ones are removed after a new one.
PRE_UPGRADE_KEPT = 3
LOCK_FILE = "locacontrol.lock"
# Written after the first successful preparation: from then on a missing database is an error.
MARKER = "locacontrol.installed"
# Written while serving and removed only at a normal end (REL-P1E-02).
PID_FILE = "locacontrol.pid"
# Created by `LocaControl.exe parar`: the running server finishes what it is doing and exits.
STOP_FILE = "locacontrol.stop"
# Present only while a schema upgrade runs: found at a start, the upgrade was interrupted.
UPGRADE_MARKER = "atualizacao-em-andamento.json"


class AlreadyRunning(RuntimeError):
    pass


class DataUnavailable(RuntimeError):
    pass


class NoSpace(RuntimeError):
    pass


class DatabaseDamaged(RuntimeError):
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
    marker = data_root() / UPGRADE_MARKER
    write_durably(
        marker,
        json.dumps(
            {
                "copy": str(copy) if copy else None,
                "new_database": copy is None,
                "from": sorted(current),
                "started": datetime.now().isoformat(timespec="seconds"),
            }
        ).encode("utf-8"),
    )
    print("Aplicando atualizações do banco de dados...", flush=True)
    command.upgrade(config, "head")  # one SQLite transaction (migrations/env.py)
    marker.unlink(missing_ok=True)
    return copy


def integrity(database: Path) -> str:
    """PRAGMA integrity_check ("ok" or the problems found); opening the file also rolls back a
    transaction left unfinished. A file SQLite cannot even read reports its error."""
    try:
        connection = sqlite3.connect(database)
        try:
            return "\n".join(row[0] for row in connection.execute("PRAGMA integrity_check"))
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        return f"erro ao ler o banco: {error}"


def remove_partial_backups(settings: Settings, database: Path) -> int:
    """Hidden work files of a backup or import cut short by an unclean end (never a finished set).
    Only called while this process holds the installation lock, so nothing is writing them."""
    saved = saved_limits(database)
    folders = {Path(settings.backup_directory)}
    for key in ("directory", "mirror_directory"):
        if saved.get(key):
            folders.add(Path(saved[key]))
    removed = 0
    for folder in folders:
        for pattern in (".locacontrol_*", ".import-*.part"):
            try:
                for path in folder.glob(pattern):
                    path.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                continue
    return removed


def revision(database: Path) -> set[str]:
    connection = sqlite3.connect(database)
    try:
        return {row[0] for row in connection.execute("SELECT version_num FROM alembic_version")}
    except sqlite3.Error:
        return set()
    finally:
        connection.close()


def sidecars(database: Path) -> list[Path]:
    return [database.with_name(database.name + suffix) for suffix in ("-journal", "-wal", "-shm")]


def restore_copy(copy: Path, database: Path):
    """The pre-upgrade copy back in place. Its journal is dropped first: a journal left by the
    interrupted upgrade must never be rolled back into the restored file."""
    part = database.with_name(database.name + ".restaurando")
    shutil.copyfile(copy, part)
    fsync_file(part)
    for path in sidecars(database):
        path.unlink(missing_ok=True)
    os.replace(part, database)


def recover_interrupted_upgrade(settings: Settings, root: Path) -> str | None:
    """A schema upgrade that did not finish (process killed, power loss, failed migration).

    The server serves nothing while it migrates, so the copy taken right before the upgrade holds
    exactly the data of that moment: putting it back loses nothing, whatever state the upgrade
    left. Without a usable copy, the database is accepted only if it is intact and at the old or
    at the new revision; otherwise nothing is touched and the start is refused.
    """
    marker = root / UPGRADE_MARKER
    if not marker.exists():
        return None
    try:
        info = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        info = {}
    database = database_file(settings)
    copy = Path(info["copy"]) if info.get("copy") else None
    if database is None:
        message = "Atualização interrompida anterior ignorada (banco que não é arquivo SQLite)."
    elif copy and copy.is_file() and integrity(copy) == "ok":
        restore_copy(copy, database)
        message = (
            "A atualização anterior do banco foi interrompida. O banco voltou à cópia feita "
            f"imediatamente antes dela ({copy.name}), sem perda de dados; a atualização será "
            "refeita agora."
        )
    elif info.get("new_database"):
        for path in (database, *sidecars(database)):
            path.unlink(missing_ok=True)
        message = "A criação do banco foi interrompida; ele será criado de novo (estava vazio)."
    else:
        config = Config(str(resource("backend/alembic.ini")))
        heads = set(ScriptDirectory.from_config(config).get_heads())
        known = {frozenset(info.get("from", [])), frozenset(heads)}
        if not (
            database.is_file()
            and integrity(database) == "ok"
            and frozenset(revision(database)) in known
        ):
            raise DatabaseDamaged(
                "A atualização anterior do banco foi interrompida e a cópia feita antes dela não "
                f"está disponível ({copy or 'sem registro'}). Nada foi alterado. Restaure um "
                "backup (docs/ADMIN_GUIDE.md, restauração manual) ou procure o suporte."
            )
        message = "A atualização anterior foi interrompida; o banco está íntegro e será atualizado."
    marker.unlink(missing_ok=True)
    return message


def check_after_unclean_end(settings: Settings, root: Path) -> str | None:
    """The PID file outlives the server only when it did not end normally (forced stop, crash,
    power loss). SQLite's journal makes each transaction atomic, but that is checked, not
    assumed: integrity_check must pass before anything is served."""
    pid_file = root / PID_FILE
    if not pid_file.exists():
        return None
    database = database_file(settings)
    if database is None or not database.is_file():
        pid_file.unlink(missing_ok=True)
        return None
    result = integrity(database)
    if result != "ok":
        raise DatabaseDamaged(
            "O LocaControl não foi encerrado normalmente e o banco falhou na verificação de "
            f"integridade ({result[:200]}). Nada foi servido nem alterado. Restaure o backup mais "
            "recente (docs/ADMIN_GUIDE.md) antes de voltar a usar o sistema."
        )
    removed = remove_partial_backups(settings, database)
    pid_file.unlink(missing_ok=True)
    return (
        "O LocaControl não foi encerrado normalmente da última vez; o banco foi verificado e "
        "está íntegro."
        + (f" {removed} arquivo(s) de backup incompleto(s) removido(s)." if removed else "")
    )


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


def listeners(settings: Settings, port: int, https_port: int, tls_files=None) -> list[dict]:
    """Where the server listens (P1-E): plain HTTP only on 127.0.0.1 (this computer); the store
    network only over HTTPS, only in the network mode and only with usable certificates."""
    http = {"host": "127.0.0.1", "port": port}
    if not (settings.local_mode and settings.network_mode):
        if settings.network_mode:
            print("LOCACONTROL_NETWORK_MODE exige LOCACONTROL_LOCAL_MODE; ignorado.", flush=True)
        return [http]
    if not tls_files:
        return [http]  # fail closed: no certificate, no store network
    certfile, keyfile, password = tls_files
    return [
        http,
        {
            "host": "0.0.0.0",
            "port": https_port,
            "ssl_certfile": certfile,
            "ssl_keyfile": keyfile,
            "ssl_keyfile_password": password,
        },
    ]


def prepare_tls(settings: Settings):
    """Creates the local CA on the first start of the network mode and renews the server
    certificate; any problem keeps the store network closed (the main computer still works)."""
    if not (settings.local_mode and settings.network_mode):
        return None
    from app.network.stations import PRIVATE_NETWORKS, registry_for, station_networks
    from app.network.tls import TLS_FOLDER, LocalAuthority, local_names, private_addresses

    registry = registry_for(settings)
    extra = [n for n in station_networks(settings) if n not in PRIVATE_NETWORKS]
    authority = LocalAuthority(registry.path.parent / TLS_FOLDER)
    try:
        server_id = (registry.server() or {}).get("id", "")[:8]
        state = authority.ensure(
            local_names(settings.station_hosts),
            private_addresses(extra),
            label=f"({server_id})",
            networks=extra,
        )
        print(
            f"HTTPS da rede: autoridade {state['ca_fingerprint'][:23]}…, certificado até "
            f"{state['server_expires'][:10]} ({state['protection']}).",
            flush=True,
        )
        return authority.server_files()
    except Exception as error:  # noqa: BLE001 — any failure keeps the network closed
        print(
            f"HTTPS indisponível ({error}). A rede da loja fica fechada; este computador continua "
            "funcionando em http://127.0.0.1.",
            file=sys.stderr,
            flush=True,
        )
        return None


def serve(app, endpoints: list[dict], stop_requested=None, on_started=None):
    """One process, one application, one or two listeners. The first runs the application's
    lifespan; the second starts after it and the two stop together.

    `stop_requested()` is polled; when true the listeners stop accepting and uvicorn waits for the
    requests in progress before the lifespan ends (which waits for backups). `on_started()` runs
    once every listener accepts connections."""
    import asyncio

    import uvicorn

    servers = [
        uvicorn.Server(uvicorn.Config(app, lifespan="on" if index == 0 else "off", **endpoint))
        for index, endpoint in enumerate(endpoints)
    ]

    async def watch():
        announced = False
        while not all(server.should_exit for server in servers):
            if not announced and all(server.started for server in servers):
                announced = True
                if on_started:
                    on_started()
            if stop_requested and stop_requested():
                print("Encerramento pedido: terminando o que está em andamento...", flush=True)
                for server in servers:
                    server.should_exit = True
                return
            await asyncio.sleep(0.25)

    async def run():
        first = asyncio.create_task(servers[0].serve())
        while not servers[0].started and not first.done():
            await asyncio.sleep(0.05)
        tasks = [first] + [asyncio.create_task(server.serve()) for server in servers[1:]]
        watcher = asyncio.create_task(watch())
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for server in servers:
            server.should_exit = True
        await asyncio.gather(*tasks, return_exceptions=True)
        watcher.cancel()

    asyncio.run(run())


def main(argv: list[str] | None = None, stop_event=None, on_started=None) -> int:
    """`stop_event` (threading.Event) and `on_started` come from the Windows service host."""
    parser = argparse.ArgumentParser(description="Servidor do LocaControl")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--https-port", type=int, default=None)
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
        (root / STOP_FILE).unlink(missing_ok=True)  # a request left from a previous run
        settings = Settings()
        try:
            check_database(settings, root)
        except DataUnavailable as error:
            print(error, file=sys.stderr, flush=True)
            return EXIT_DATA_UNAVAILABLE
        try:
            for message in (
                recover_interrupted_upgrade(settings, root),
                check_after_unclean_end(settings, root),
            ):
                if message:
                    print(message, flush=True)
        except DatabaseDamaged as error:
            print(error, file=sys.stderr, flush=True)
            return EXIT_DATABASE_DAMAGED
        try:
            prepare(settings)
        except NoSpace as error:
            print(error, file=sys.stderr, flush=True)
            return EXIT_NO_SPACE
        except Exception as error:
            # A failed migration: undone now from the copy, so no half-upgraded database is left.
            print(f"A atualização do banco falhou: {error}", file=sys.stderr, flush=True)
            try:
                message = recover_interrupted_upgrade(settings, root)
            except DatabaseDamaged as damaged:
                print(damaged, file=sys.stderr, flush=True)
                return EXIT_DATABASE_DAMAGED
            if message:
                print(
                    message.replace(" será refeita agora", " será tentada no próximo início"),
                    file=sys.stderr,
                    flush=True,
                )
            raise
        (root / MARKER).touch()
        if args.prepare:
            return 0
        own = [f"http://127.0.0.1:{args.port}", f"http://localhost:{args.port}"]
        settings.allowed_origins += [o for o in own if o not in settings.allowed_origins]
        https_port = args.https_port or settings.https_port
        endpoints = listeners(settings, args.port, https_port, prepare_tls(settings))
        if len(endpoints) > 1:
            print(f"Rede da loja: estações em https://<este computador>:{https_port}/", flush=True)
        from app.main import create_app

        stop_file = root / STOP_FILE

        def stop_requested() -> bool:
            return stop_file.exists() or bool(stop_event and stop_event.is_set())

        (root / PID_FILE).write_text(str(os.getpid()), encoding="ascii")
        serve(create_app(settings), endpoints, stop_requested, on_started)
        # Only a normal end removes it: left behind, the next start checks the database.
        (root / PID_FILE).unlink(missing_ok=True)
        stop_file.unlink(missing_ok=True)
        print("LocaControl encerrado normalmente.", flush=True)
        return 0
    finally:
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
