"""Backup sets: one zip with a consistent database copy, every stored file and a manifest.

Restoring never deletes: the current state is backed up first and replaced folders are moved
aside. Only SQLite file databases are supported here.
"""

import hashlib
import json
import logging
import re
import shutil
import sqlite3
import threading
import zipfile
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import __version__
from app.contracts.models import AppSetting
from app.core.clock import BUSINESS_TZ
from app.core.config import PROJECT_ROOT
from app.persistence.database import resolve_database_url

logger = logging.getLogger(__name__)
# One backup or restore at a time in this process, including the scheduler.
OPERATION_LOCK = threading.RLock()
NAME = re.compile(r"^locacontrol_(\d{4}-\d{2}-\d{2})_(\d{6})(_pre-restore)?\.zip$")
SETTING_KEY = "backup"
DEFAULTS = {"enabled": False, "time": "22:00", "keep": 14, "directory": ""}
DATABASE_MEMBER = "locacontrol.db"
MANIFEST = "manifest.json"


def volume(path: Path):
    """Device id of the nearest existing ancestor; data folders may not exist yet."""
    for candidate in (Path(path), *Path(path).parents):
        if candidate.exists():
            return candidate.stat().st_dev
    return None


def sha256(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1 << 20), b""):
        digest.update(chunk)
    return digest.hexdigest()


def due(config: dict, now: datetime, names: list[str]) -> bool:
    """True when the daily backup time has passed and no regular set exists for today."""
    if not config["enabled"]:
        return False
    hour, minute = (int(part) for part in config["time"].split(":"))
    if (now.hour, now.minute) < (hour, minute):
        return False
    today, since = now.strftime("%Y-%m-%d"), f"{hour:02d}{minute:02d}00"
    # A set made earlier in the day (a manual one, for instance) does not cover the day's work.
    return not any(
        (match := NAME.match(name)) and match[1] == today and match[2] >= since and not match[3]
        for name in names
    )


class BackupManager:
    def __init__(self, settings, engine):
        self.settings = settings
        self.engine = engine

    # ---- locations -----------------------------------------------------------------

    def database_path(self) -> Path:
        url = resolve_database_url(self.settings.database_url)
        if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
            raise HTTPException(
                409, "Backup pelo sistema está disponível apenas para SQLite local."
            )
        return Path(url.database)

    def folders(self) -> dict[str, Path]:
        return {
            "imports": Path(self.settings.import_directory),
            "documents": Path(self.settings.document_directory),
            "fiscal": Path(self.settings.fiscal_directory),
        }

    def config(self, db) -> dict:
        row = db.get(AppSetting, SETTING_KEY)
        return {**DEFAULTS, **(row.value if row else {})}

    def directory(self, config: dict) -> Path:
        return Path(config["directory"] or self.settings.backup_directory)

    def path(self, config: dict, name: str) -> Path:
        # The pattern is the whole defence against path traversal: no separators can match.
        path = self.directory(config) / name
        if not NAME.match(name) or not path.is_file():
            raise HTTPException(404, "Backup não encontrado.")
        return path

    def listing(self, config: dict) -> list[dict]:
        directory = self.directory(config)
        if not directory.is_dir():
            return []
        items = []
        for path in directory.iterdir():
            match = NAME.match(path.name)
            if match and path.is_file():
                stat = path.stat()
                items.append(
                    {
                        "name": path.name,
                        "size": stat.st_size,
                        "created_at": int(stat.st_mtime),
                        "kind": "pre-restore" if match[3] else "backup",
                    }
                )
        return sorted(items, key=lambda item: item["name"], reverse=True)

    # ---- create and verify ---------------------------------------------------------

    def create(self, config: dict, kind: str = "manual") -> dict:
        with OPERATION_LOCK:
            return self._create(config, kind)

    def _create(self, config: dict, kind: str) -> dict:
        database = self.database_path()
        directory = self.directory(config)
        directory.mkdir(parents=True, exist_ok=True)
        now = datetime.now(BUSINESS_TZ)
        suffix = "_pre-restore" if kind == "pre-restore" else ""
        name = f"locacontrol_{now:%Y-%m-%d_%H%M%S}{suffix}.zip"
        target = directory / name
        if target.exists():
            raise HTTPException(409, "Já existe um backup deste mesmo segundo. Tente novamente.")
        copy_path, part = directory / f".{name}.db", directory / f".{name}.part"
        try:
            source = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
            copy = sqlite3.connect(copy_path)
            try:
                # SQLite's online backup gives a consistent copy while the system is in use.
                source.backup(copy)
                check = copy.execute("PRAGMA integrity_check").fetchone()[0]
                revision = copy.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            finally:
                copy.close()
                source.close()
            if check != "ok":
                raise HTTPException(500, "A cópia do banco falhou na verificação de integridade.")
            members = {DATABASE_MEMBER: copy_path}
            for label, folder in self.folders().items():
                if folder.is_dir():
                    for file in sorted(p for p in folder.rglob("*") if p.is_file()):
                        members[f"{label}/{file.relative_to(folder).as_posix()}"] = file
            hashes = {}
            with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as archive:
                for member, file in members.items():
                    with file.open("rb") as stream:
                        hashes[member] = sha256(stream)
                    archive.write(file, member)
                manifest = {
                    "format": 1,
                    "kind": kind,
                    "created_at": now.isoformat(timespec="seconds"),
                    "revision": revision,
                    "app_version": __version__,
                    "files": hashes,
                }
                archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=1))
            part.replace(target)
        finally:
            copy_path.unlink(missing_ok=True)
            part.unlink(missing_ok=True)
        logger.info("Backup criado: %s (%s arquivos)", name, len(hashes))
        if kind != "pre-restore":
            self.prune(config)
        return {"name": name, "size": target.stat().st_size, "kind": kind, "revision": revision}

    def prune(self, config: dict):
        """Retention applies to regular sets only; safety copies made by a restore are kept."""
        regular = [item for item in self.listing(config) if item["kind"] == "backup"]
        for item in regular[max(int(config["keep"]), 1) :]:
            (self.directory(config) / item["name"]).unlink(missing_ok=True)
            logger.info("Backup removido pela retenção: %s", item["name"])

    def verify(self, path: Path) -> dict:
        errors, manifest, revision, users = [], {}, None, None
        scratch = path.with_name(f".{path.name}.verify.db")
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if MANIFEST not in names:
                    errors.append("Manifesto ausente.")
                else:
                    manifest = json.loads(archive.read(MANIFEST))
                    listed = set(manifest.get("files", {}))
                    if DATABASE_MEMBER not in listed:
                        errors.append("Banco de dados fora do manifesto.")
                    extra = {n for n in names if not n.endswith("/")} - listed - {MANIFEST}
                    if extra:
                        errors.append(f"Arquivos fora do manifesto: {len(extra)}.")
                    for member, expected in manifest.get("files", {}).items():
                        if member not in names:
                            errors.append(f"Arquivo ausente: {member}")
                            continue
                        with archive.open(member) as stream:
                            if sha256(stream) != expected:
                                errors.append(f"Conteúdo alterado: {member}")
                if DATABASE_MEMBER not in names:
                    errors.append("Banco de dados ausente.")
                else:
                    with archive.open(DATABASE_MEMBER) as source, scratch.open("wb") as out:
                        shutil.copyfileobj(source, out)
                    connection = sqlite3.connect(scratch)
                    try:
                        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                            errors.append("Banco de dados corrompido.")
                        revision = connection.execute(
                            "SELECT version_num FROM alembic_version"
                        ).fetchone()[0]
                        users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                        if not users:
                            errors.append("Banco de dados sem nenhum usuário.")
                    finally:
                        connection.close()
        except (zipfile.BadZipFile, sqlite3.DatabaseError, json.JSONDecodeError, KeyError):
            errors.append("Arquivo de backup inválido ou ilegível.")
        finally:
            scratch.unlink(missing_ok=True)
        return {
            "name": path.name,
            "ok": not errors,
            "errors": errors,
            "revision": revision,
            "users": users,
            "created_at": manifest.get("created_at"),
            "kind": manifest.get("kind"),
            "app_version": manifest.get("app_version"),
            "files": len(manifest.get("files", {})),
        }

    # ---- restore -------------------------------------------------------------------

    def migrations(self) -> ScriptDirectory:
        return ScriptDirectory(str(PROJECT_ROOT / "backend" / "migrations"))

    def _extract_database(self, archive: zipfile.ZipFile, target: Path):
        with archive.open(DATABASE_MEMBER) as source, target.open("wb") as out:
            shutil.copyfileobj(source, out)

    def _overwrite_database(self, source_path: Path):
        self.engine.dispose()
        source = sqlite3.connect(source_path)
        live = sqlite3.connect(self.database_path(), timeout=10)
        try:
            source.backup(live)
        finally:
            source.close()
            live.close()

    def _undo(self, safety: Path, scratch, staging, replaced, moved, placed):
        """Puts back the folders moved aside and the database saved in the safety copy."""
        for label in placed:
            shutil.move(str(self.folders()[label]), str(staging / label))
        for label in moved:
            shutil.move(str(replaced / label), str(self.folders()[label]))
        if replaced.is_dir() and not any(replaced.iterdir()):
            replaced.rmdir()
        with zipfile.ZipFile(safety) as archive:
            self._extract_database(archive, scratch)
        self._overwrite_database(scratch)

    def restore(self, config: dict, name: str) -> dict:
        """Caller must have released its own database transaction before calling this."""
        path = self.path(config, name)
        report = self.verify(path)
        if not report["ok"]:
            raise HTTPException(
                409, "Backup reprovado na verificação: " + " ".join(report["errors"])
            )
        scripts = self.migrations()
        if report["revision"] not in {rev.revision for rev in scripts.walk_revisions()}:
            raise HTTPException(
                409,
                "Este backup foi criado por uma versão mais nova ou desconhecida do sistema. "
                "Atualize o LocaControl antes de restaurá-lo.",
            )
        self.database_path()  # SQLite only, checked before anything is touched
        # shortcut: restore moves folders by rename, so it needs one volume; stage per volume to
        # support a backup folder on another disk.
        backups = volume(self.directory(config))
        apart = [label for label, folder in self.folders().items() if volume(folder) != backups]
        if apart:
            raise HTTPException(
                409,
                "Restauração indisponível: a pasta de backups está em outro disco que os dados ("
                + ", ".join(apart)
                + "). Copie o arquivo de backup para uma pasta no mesmo disco dos dados, "
                "configure-a como pasta de backups e restaure de lá. Nada foi alterado.",
            )
        head = scripts.get_current_head()
        with OPERATION_LOCK:
            safety = self.create(config, "pre-restore")
            stamp = datetime.now(BUSINESS_TZ).strftime("%Y-%m-%d_%H%M%S")
            directory = self.directory(config)
            replaced, staging = directory / f"replaced_{stamp}", directory / f".restore_{stamp}"
            scratch = path.with_name(f".{path.name}.restore.db")
            # What has been changed so far, so a failure can be undone step by step.
            touched, moved, placed = False, [], []
            try:
                with zipfile.ZipFile(path) as archive:
                    # Everything is unpacked and checked before the live data is touched.
                    self._extract_database(archive, scratch)
                    for label in self.folders():
                        root = (staging / label).resolve()
                        root.mkdir(parents=True, exist_ok=True)
                        for member in archive.namelist():
                            if not member.startswith(label + "/") or member.endswith("/"):
                                continue
                            destination = (root / member[len(label) + 1 :]).resolve()
                            if root not in destination.parents:
                                raise HTTPException(
                                    409, "Backup contém caminho de arquivo inválido."
                                )
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            with archive.open(member) as source, destination.open("wb") as out:
                                shutil.copyfileobj(source, out)
                touched = True
                self._overwrite_database(scratch)
                for label, folder in self.folders().items():
                    if folder.exists():
                        # Moved aside, never deleted: nothing stored after the backup is lost.
                        replaced.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(folder), str(replaced / label))
                        moved.append(label)
                    folder.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(staging / label), str(folder))
                    placed.append(label)
                if report["revision"] != head:
                    self.engine.dispose()
                    migration = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
                    migration.attributes["database_url"] = self.settings.database_url
                    command.upgrade(migration, "head")
            except Exception as error:
                if not touched and isinstance(error, HTTPException):
                    raise
                logger.exception("Falha ao restaurar %s", name)
                if touched:
                    try:
                        self._undo(
                            directory / safety["name"], scratch, staging, replaced, moved, placed
                        )
                    except Exception:
                        logger.exception("Falha ao desfazer a restauração de %s", name)
                        raise HTTPException(
                            500,
                            "A restauração falhou e não foi possível voltar sozinha ao estado "
                            "anterior. Restaure manualmente a cópia de segurança "
                            f"{safety['name']} para voltar ao ponto de partida.",
                        ) from error
                    logger.warning("Restauração de %s desfeita: estado anterior recolocado.", name)
                raise HTTPException(
                    500,
                    "A restauração falhou e foi desfeita automaticamente: nada foi alterado. "
                    f"O motivo ficou registrado no log (cópia de segurança {safety['name']}).",
                ) from error
            finally:
                scratch.unlink(missing_ok=True)
                shutil.rmtree(staging, ignore_errors=True)
                self.engine.dispose()
        logger.warning("Backup restaurado: %s (cópia prévia %s)", name, safety["name"])
        return {
            "restored": name,
            "safety_backup": safety["name"],
            "revision": report["revision"],
            "upgraded_to": head if report["revision"] != head else None,
            "replaced_files": replaced.name if replaced.exists() else None,
        }


class BackupScheduler(threading.Thread):
    """Checks once a minute whether today's automatic backup is due."""

    def __init__(self, manager: BackupManager, interval: float = 60):
        super().__init__(name="locacontrol-backup", daemon=True)
        self.manager = manager
        self.interval = interval
        self.stop_event = threading.Event()

    def tick(self, now: datetime | None = None) -> dict | None:
        with Session(self.manager.engine) as db:
            config = self.manager.config(db)
        names = [item["name"] for item in self.manager.listing(config)]
        if due(config, now or datetime.now(BUSINESS_TZ), names):
            return self.manager.create(config, "auto")
        return None

    def run(self):
        while not self.stop_event.wait(self.interval):
            try:
                self.tick()
            except Exception:  # noqa: BLE001 — a failed backup must not stop later attempts
                logger.exception("Falha no backup automático.")

    def stop(self):
        self.stop_event.set()
