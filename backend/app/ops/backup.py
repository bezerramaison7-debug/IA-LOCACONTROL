"""Backup sets: one zip with a consistent database copy, every stored file and a manifest.

Restoring never deletes: the current state is backed up first and replaced folders are moved
aside, next to the data folders (so the backup folder may live on another disk). Only SQLite
file databases are supported here.

Automatic protection (ADR-024): every 20 minutes by default (60 or daily on request), a record
of every run beside the database, retention of recent and daily copies, an optional second
copy in another folder and import of a set kept elsewhere.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import __version__
from app.contracts.models import AppSetting
from app.core.clock import BUSINESS_TZ
from app.core.config import resource
from app.ops.storage import LIMIT_DEFAULTS, cap_bytes, plan, removal_order, reserve_bytes
from app.persistence.database import resolve_database_url

logger = logging.getLogger(__name__)
# One backup or restore at a time in this process, including the scheduler.
OPERATION_LOCK = threading.RLock()
# Regular sets have no suffix; safety copies and imported sets are never pruned.
NAME = re.compile(r"^locacontrol_(\d{4}-\d{2}-\d{2})_(\d{6})(_pre-restore|_importado)?\.zip$")
SUFFIX_KINDS = {"": "backup", "_pre-restore": "pre-restore", "_importado": "imported"}
SETTING_KEY = "backup"
FREQUENCIES = {"20min": 20, "60min": 60, "daily": None}
# A new installation (no saved row) is protected from the start: every 20 minutes.
DEFAULTS = {
    "enabled": True,
    "frequency": "20min",
    "time": "22:00",
    "keep": 14,
    "directory": "",
    "mirror_directory": "",
    # Storage limits (A3): cap of the backup folder and free space kept on its disk.
    **LIMIT_DEFAULTS,
}
# Rows saved before ADR-024 had no frequency: they keep their daily schedule.
LEGACY_FREQUENCY = "daily"
DATABASE_MEMBER = "locacontrol.db"
MANIFEST = "manifest.json"
# Every regular set of the last day is kept, besides the newest set of each of `keep` days.
RECENT_HOURS = 24
# After a failed automatic run, try again after this many minutes (or the interval, if shorter).
RETRY_MINUTES = 5
HISTORY_FILE = "backup-history.json"
HISTORY_LIMIT = 100
# An imported set larger than this is refused before it fills the disk.
IMPORT_MAX_BYTES = 8 * 1024**3


def sha256(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1 << 20), b""):
        digest.update(chunk)
    return digest.hexdigest()


def moment(match: re.Match) -> datetime:
    return datetime.strptime(match[1] + match[2], "%Y-%m-%d%H%M%S").replace(tzinfo=BUSINESS_TZ)


def regular_moments(names: list[str]) -> list[datetime]:
    return sorted(moment(match) for name in names if (match := NAME.match(name)) and not match[3])


def due(config: dict, now: datetime, names: list[str], unchanged_at: datetime | None = None):
    """True when an automatic backup should run now.

    Interval: the newest regular set (manual ones count) or the last "nothing changed" check is
    at least one interval old. Daily: the configured time has passed and no regular set exists
    for today since that time.
    """
    if not config["enabled"]:
        return False
    minutes = FREQUENCIES.get(config.get("frequency", LEGACY_FREQUENCY))
    if minutes:
        moments = regular_moments(names) + ([unchanged_at] if unchanged_at else [])
        return not moments or now - max(moments) >= timedelta(minutes=minutes)
    hour, minute = (int(part) for part in config["time"].split(":"))
    if (now.hour, now.minute) < (hour, minute):
        return False
    today, since = now.strftime("%Y-%m-%d"), f"{hour:02d}{minute:02d}00"
    # A set made earlier in the day (a manual one, for instance) does not cover the day's work.
    return not any(
        (match := NAME.match(name)) and match[1] == today and match[2] >= since and not match[3]
        for name in names
    )


def retained(names: list[str], keep: int, now: datetime) -> set[str]:
    """Regular sets kept: all from the last RECENT_HOURS, plus the newest of each of the
    `keep` most recent days. With one set a day this is the former "keep N sets"."""
    regular = sorted(
        ((moment(match), name) for name in names if (match := NAME.match(name)) and not match[3]),
        reverse=True,
    )
    keep_names = {name for when, name in regular if now - when < timedelta(hours=RECENT_HOURS)}
    days: dict[str, str] = {}
    for when, name in regular:
        days.setdefault(when.strftime("%Y-%m-%d"), name)
    for day in sorted(days, reverse=True)[: max(int(keep), 1)]:
        keep_names.add(days[day])
    return keep_names


def now_iso() -> str:
    return datetime.now(BUSINESS_TZ).isoformat(timespec="seconds")


# Space refusals are retried less often: the disk rarely frees itself within minutes.
SPACE_RETRY_MINUTES = 60
SPACE_STATUS = 507


class BackupManager:
    # Replaceable in tests to simulate small and large disks.
    disk_usage = staticmethod(shutil.disk_usage)

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
        if row is None:
            return dict(DEFAULTS)
        return {**DEFAULTS, "frequency": LEGACY_FREQUENCY, **row.value}

    def directory(self, config: dict) -> Path:
        return Path(config["directory"] or self.settings.backup_directory)

    def path(self, config: dict, name: str) -> Path:
        # The pattern is the whole defence against path traversal: no separators can match.
        path = self.directory(config) / name
        if not NAME.match(name) or not path.is_file():
            raise HTTPException(404, "Backup não encontrado.")
        return path

    def listing(self, config: dict, directory: Path | None = None) -> list[dict]:
        directory = directory or self.directory(config)
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
                        "kind": SUFFIX_KINDS[match[3] or ""],
                    }
                )
        return sorted(items, key=lambda item: item["name"], reverse=True)

    # ---- run history (a file beside the database, so it survives restores) ----------

    def history_path(self) -> Path:
        return self.database_path().parent / HISTORY_FILE

    def history(self) -> dict:
        try:
            data = json.loads(self.history_path().read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, HTTPException):
            return {}

    def _save_history(self, data: dict):
        path = self.history_path()
        part = path.with_name(f".{path.name}.part")
        part.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        part.replace(path)

    def record(self, run: dict, **extra):
        """Appends one run; never lets a bookkeeping error hide the backup's own result."""
        try:
            data = self.history()
            data["runs"] = ([run] + data.get("runs", []))[:HISTORY_LIMIT]
            data["last_" + ("success" if run["status"] == "ok" else "failure")] = run
            data.update(extra)
            self._save_history(data)
        except (OSError, HTTPException):
            logger.exception("Não foi possível registrar o histórico do backup.")

    def fingerprint(self) -> str:
        """Changes whenever the database file or any stored file changes (size or mtime)."""
        digest = hashlib.sha256()
        database = self.database_path()
        for path in (database, database.with_name(database.name + "-wal")):
            if path.exists():
                stat = path.stat()
                digest.update(f"{path.name}|{stat.st_size}|{stat.st_mtime_ns}\n".encode())
        for label, folder in self.folders().items():
            if folder.is_dir():
                for file in sorted(p for p in folder.rglob("*") if p.is_file()):
                    stat = file.stat()
                    relative = file.relative_to(folder).as_posix()
                    digest.update(
                        f"{label}/{relative}|{stat.st_size}|{stat.st_mtime_ns}\n".encode()
                    )
        return digest.hexdigest()

    def status(self, config: dict, now: datetime | None = None) -> dict:
        """What the Backups screen and the dashboard show, including the warning to raise."""
        now = now or datetime.now(BUSINESS_TZ)
        data = self.history()
        runs = data.get("runs", [])
        success, failure = data.get("last_success"), data.get("last_failure")
        minutes = FREQUENCIES.get(config.get("frequency"))
        alert = None
        last_ok = datetime.fromisoformat(success["finished_at"]) if success else None
        # The newest run decides: a success after a failure clears the warning.
        failed_last = bool(runs) and runs[0]["status"] == "failed"
        if failed_last:
            alert = {
                "level": "danger",
                "message": "A última tentativa de backup falhou ("
                + datetime.fromisoformat(failure["finished_at"]).strftime("%d/%m/%Y %H:%M")
                + "): "
                + failure.get("error", "motivo registrado no log")
                + " Confira a pasta de backups e faça um backup agora.",
            }
        elif not config["enabled"]:
            alert = {
                "level": "warning",
                "message": "O backup automático está desativado. Os dados só ficam protegidos "
                "pelos backups feitos manualmente.",
            }
        elif last_ok is None:
            alert = {"level": "warning", "message": "Nenhum backup concluído ainda."}
        elif minutes and now - last_ok > timedelta(minutes=3 * minutes):
            # Unchanged data is checked, not copied again: that check also counts as coverage.
            checked = data.get("unchanged_at")
            if not checked or now - datetime.fromisoformat(checked) > timedelta(
                minutes=3 * minutes
            ):
                alert = {
                    "level": "warning",
                    "message": "O último backup concluído é de "
                    + last_ok.strftime("%d/%m/%Y %H:%M")
                    + ". O backup automático só roda com este computador e o LocaControl "
                    "ligados.",
                }
        space = self.storage(config)
        if alert is None and space.get("available") and not space["fits"]:
            alert = {"level": "warning", "message": "O próximo backup não cabe: " + space["reason"]}
        mirror = (success or {}).get("mirror") or {}
        if alert is None and config.get("mirror_directory") and mirror.get("status") == "failed":
            alert = {
                "level": "warning",
                "message": "O último backup foi concluído, mas a segunda cópia falhou: "
                + mirror.get("error", "")
                + " Confira se o outro disco está conectado.",
            }
        return {
            "last_success": success,
            "last_failure": failure,
            "unchanged_at": data.get("unchanged_at"),
            "runs": runs[:20],
            "alert": alert,
            "storage": space,
            "requires_running": "O backup automático só acontece enquanto este computador e "
            "o LocaControl estão ligados. Com o computador desligado, nenhuma cópia é feita.",
        }

    # ---- storage limits (A3) ---------------------------------------------------------

    def estimate(self) -> tuple[int, int]:
        """Upper bound of the next set and its peak (the temporary database copy on top)."""
        database = self.database_path()
        db_size = database.stat().st_size if database.exists() else 0
        files = sum(
            p.stat().st_size
            for folder in self.folders().values()
            if folder.is_dir()
            for p in folder.rglob("*")
            if p.is_file()
        )
        estimate = db_size + files + 64 * 1024  # manifest and zip headers
        return estimate, estimate + db_size

    def storage_plan(self, config: dict, directory: Path, estimate: int, peak: int, bounded=True):
        items = self.listing(config, directory)
        managed = sum(item["size"] for item in items)
        regular = []
        days: dict[str, str] = {}
        for item in sorted(items, key=lambda i: i["name"]):
            match = NAME.match(item["name"])
            if not match[3]:
                days[match[1]] = item["name"]  # last one of each day wins: the newest
        for item in items:
            match = NAME.match(item["name"])
            if not match[3]:
                regular.append(
                    (
                        item["name"],
                        item["size"],
                        match[1] + match[2],
                        days[match[1]] == item["name"],
                    )
                )
        usage = self.disk_usage(directory)
        return plan(
            estimate=estimate,
            peak=peak,
            free=usage.free,
            disk_total=usage.total,
            managed=managed,
            removable=removal_order(regular),
            config=config,
            bounded=bounded,
        )

    def make_room(self, directory: Path, decision) -> list[str]:
        for name in decision.remove:
            (directory / name).unlink(missing_ok=True)
            logger.warning("Backup removido para respeitar o limite de espaço: %s", name)
        return decision.remove

    def storage(self, config: dict) -> dict:
        """What the screen shows: room left, the cap and whether the next set fits."""
        directory = self.directory(config)
        try:
            probe = (
                directory
                if directory.is_dir()
                else next(p for p in (directory, *directory.parents) if p.exists())
            )
            estimate, peak = self.estimate()
            usage = self.disk_usage(probe)
            decision = (
                self.storage_plan(config, directory, estimate, peak)
                if directory.is_dir()
                else plan(
                    estimate=estimate,
                    peak=peak,
                    free=usage.free,
                    disk_total=usage.total,
                    managed=0,
                    removable=[],
                    config=config,
                )
            )
        except (OSError, StopIteration, HTTPException) as error:
            return {"available": False, "error": describe(error)}
        return {
            "available": True,
            "managed_bytes": sum(item["size"] for item in self.listing(config)),
            "cap_bytes": cap_bytes(config),
            "free_bytes": usage.free,
            "disk_bytes": usage.total,
            "reserve_bytes": reserve_bytes(usage.total, config),
            "estimate_bytes": estimate,
            "peak_bytes": peak,
            "fits": decision.fits,
            "removes": len(decision.remove),
            "reason": decision.reason,
        }

    # ---- create and verify ---------------------------------------------------------

    def create(self, config: dict, kind: str = "manual") -> dict:
        with OPERATION_LOCK:
            started = now_iso()
            fingerprint = None
            try:
                fingerprint = self.fingerprint()
                result = self._create(config, kind)
            except Exception as error:
                message = error.detail if isinstance(error, HTTPException) else describe(error)
                self.record(
                    {
                        "started_at": started,
                        "finished_at": now_iso(),
                        "kind": kind,
                        "status": "failed",
                        "error": message,
                    }
                )
                logger.exception("Falha no backup (%s).", kind)
                if isinstance(error, HTTPException):
                    raise
                raise HTTPException(500, "O backup falhou: " + message) from error
            run = {
                "started_at": started,
                "finished_at": now_iso(),
                "kind": kind,
                "status": "ok",
                "name": result["name"],
                "size": result["size"],
            }
            if result.get("removed_for_space"):
                run["removed_for_space"] = result["removed_for_space"]
            if kind != "pre-restore":
                run["mirror"] = self.mirror(config, result["name"])
                result["mirror"] = run["mirror"]
            # The fingerprint is taken before the copy: a change made meanwhile triggers the next.
            self.record(run, fingerprint=fingerprint, unchanged_at=None)
            return result

    def _create(self, config: dict, kind: str) -> dict:
        database = self.database_path()
        directory = self.directory(config)
        directory.mkdir(parents=True, exist_ok=True)
        suffix = "_pre-restore" if kind == "pre-restore" else ""
        # Names have one-second resolution: two sets in the same second wait for the next one.
        for _ in range(15):
            now = datetime.now(BUSINESS_TZ)
            name = f"locacontrol_{now:%Y-%m-%d_%H%M%S}{suffix}.zip"
            target = directory / name
            if not target.exists():
                break
            time.sleep(0.1)
        else:
            raise HTTPException(409, "Já existe um backup deste mesmo segundo. Tente novamente.")
        # Estimate before writing (A3): refuse rather than exhaust the disk of the data.
        estimate, peak = self.estimate()
        decision = self.storage_plan(
            config, directory, estimate, peak, bounded=kind != "pre-restore"
        )
        if not decision.fits:
            raise HTTPException(SPACE_STATUS, decision.reason)
        removed = self.make_room(directory, decision)
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
        return {
            "name": name,
            "size": target.stat().st_size,
            "kind": kind,
            "revision": revision,
            "removed_for_space": removed,
        }

    def prune(self, config: dict, directory: Path | None = None):
        """Retention applies to regular sets only; safety copies and imported sets are kept."""
        directory = directory or self.directory(config)
        names = [item["name"] for item in self.listing(config, directory)]
        keep = retained(names, config["keep"], datetime.now(BUSINESS_TZ))
        for name in names:
            match = NAME.match(name)
            if not match[3] and name not in keep:
                (directory / name).unlink(missing_ok=True)
                logger.info("Backup removido pela retenção: %s", name)

    def mirror(self, config: dict, name: str) -> dict:
        """Second copy in another folder (another disk): copied, checked, then pruned there."""
        folder = config.get("mirror_directory") or ""
        if not folder:
            return {"status": "off"}
        source = self.directory(config) / name
        target = Path(folder) / name
        part = target.with_name(f".{name}.part")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            size = source.stat().st_size
            decision = self.storage_plan(config, target.parent, size, size)
            if not decision.fits:
                return {"status": "failed", "directory": folder, "error": decision.reason}
            self.make_room(target.parent, decision)
            shutil.copyfile(source, part)
            with source.open("rb") as original, part.open("rb") as copied:
                if sha256(original) != sha256(copied):
                    raise OSError("a cópia ficou diferente do original")
            part.replace(target)
            self.prune(config, Path(folder))
            return {"status": "ok", "directory": folder}
        except OSError as error:
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass  # the folder itself is gone: nothing was left behind
            logger.exception("Falha na segunda cópia do backup %s.", name)
            return {"status": "failed", "directory": folder, "error": describe(error)}

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

    # ---- import a set kept elsewhere (another disk, a USB drive, another computer) ----

    def import_set(self, config: dict, stream, filename: str) -> dict:
        """Copies an uploaded set into the backup folder, verified, as `<moment>_importado`.

        Imported sets are outside retention, so the next automatic backup never removes one
        waiting to be restored. Nothing in the live data changes here.
        """
        directory = self.directory(config)
        directory.mkdir(parents=True, exist_ok=True)
        part = directory / f".import-{uuid.uuid4().hex}.part"
        usage = self.disk_usage(directory)
        # A recovery copy may exceed the cap, never the free-space reserve (A3).
        room = usage.free - reserve_bytes(usage.total, config)
        try:
            size = 0
            with part.open("wb") as out:
                while chunk := stream.read(1 << 20):
                    size += len(chunk)
                    if size > IMPORT_MAX_BYTES:
                        raise HTTPException(413, "Arquivo grande demais para um backup.")
                    if size > room:
                        raise HTTPException(
                            SPACE_STATUS,
                            "Espaço insuficiente na pasta de backups para importar este arquivo "
                            "mantendo o espaço mínimo livre do disco. Nada foi copiado.",
                        )
                    out.write(chunk)
            report = self.verify(part)
            if not report["ok"]:
                raise HTTPException(
                    422,
                    "O arquivo não é um backup íntegro do LocaControl: "
                    + " ".join(report["errors"])
                    + " Nada foi copiado.",
                )
            try:
                created = datetime.fromisoformat(report["created_at"]).astimezone(BUSINESS_TZ)
            except (TypeError, ValueError) as error:
                raise HTTPException(422, "O backup não informa quando foi criado.") from error
            name = f"locacontrol_{created:%Y-%m-%d_%H%M%S}_importado.zip"
            with part.open("rb") as stream_copy:
                digest = sha256(stream_copy)
            for existing in (directory / name, directory / name.replace("_importado", "")):
                if existing.is_file():
                    with existing.open("rb") as current:
                        if sha256(current) == digest:
                            raise HTTPException(
                                409,
                                f"Este backup já está na pasta de backups ({existing.name}). "
                                "Restaure-o pela lista.",
                            )
            if (directory / name).exists():
                raise HTTPException(409, f"Já existe um backup importado com o nome {name}.")
            os.replace(part, directory / name)
        finally:
            part.unlink(missing_ok=True)
        logger.info("Backup importado: %s (arquivo enviado %s)", name, filename)
        return {**report, "name": name, "size": size, "original_name": filename}

    # ---- restore -------------------------------------------------------------------

    def migrations(self) -> ScriptDirectory:
        return ScriptDirectory(str(resource("backend/migrations")))

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
            shutil.move(str(self.folders()[label]), str(staging[label]))
        for label in moved:
            shutil.move(str(replaced[label]), str(self.folders()[label]))
        for folder in replaced.values():
            if folder.parent.is_dir() and not any(folder.parent.iterdir()):
                folder.parent.rmdir()
        with zipfile.ZipFile(safety) as archive:
            self._extract_database(archive, scratch)
        self._overwrite_database(scratch)

    def check_restore_space(self, config: dict, path: Path, database: Path):
        """The restore unpacks everything beside the data before swapping: that must fit on each
        data disk while keeping the free-space reserve (A3). Checked before anything changes."""
        with zipfile.ZipFile(path) as archive:
            sizes = {info.filename: info.file_size for info in archive.infolist()}
        needs: dict[Path, int] = {database.parent: sizes.get(DATABASE_MEMBER, 0)}
        for label, folder in self.folders().items():
            total = sum(size for member, size in sizes.items() if member.startswith(label + "/"))
            needs[folder.parent] = needs.get(folder.parent, 0) + total
        by_disk: dict[int, tuple[Path, int]] = {}
        for place, need in needs.items():
            anchor = next(p for p in (place, *place.parents) if p.exists())
            device = anchor.stat().st_dev
            known = by_disk.get(device, (anchor, 0))
            by_disk[device] = (known[0], known[1] + need)
        for anchor, need in by_disk.values():
            usage = self.disk_usage(anchor)
            reserve = reserve_bytes(usage.total, config)
            if usage.free - need < reserve:
                raise HTTPException(
                    SPACE_STATUS,
                    f"Espaço insuficiente para restaurar: são necessários cerca de "
                    f"{need / 1024**3:.1f} GB no disco dos dados mantendo "
                    f"{reserve / 1024**3:.1f} GB livres. Nada foi alterado.".replace(".", ","),
                )

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
        database = self.database_path()  # SQLite only, checked before anything is touched
        self.check_restore_space(config, path, database)
        head = scripts.get_current_head()
        with OPERATION_LOCK:
            safety = self.create(config, "pre-restore")
            stamp = datetime.now(BUSINESS_TZ).strftime("%Y-%m-%d_%H%M%S")
            # Staging and the replaced folders sit beside each data folder, on its own disk:
            # folders are swapped by rename there, whatever disk holds the backup set.
            staging = {
                label: folder.parent / f".restore_{stamp}" / label
                for label, folder in self.folders().items()
            }
            replaced = {
                label: folder.parent / f"replaced_{stamp}" / label
                for label, folder in self.folders().items()
            }
            scratch = database.with_name(f".{name}.restore.db")
            # What has been changed so far, so a failure can be undone step by step.
            touched, moved, placed = False, [], []
            try:
                with zipfile.ZipFile(path) as archive:
                    # Everything is unpacked and checked before the live data is touched.
                    self._extract_database(archive, scratch)
                    for label in self.folders():
                        root = staging[label]
                        root.mkdir(parents=True, exist_ok=True)
                        root = root.resolve()
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
                        replaced[label].parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(folder), str(replaced[label]))
                        moved.append(label)
                    folder.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(staging[label]), str(folder))
                    placed.append(label)
                if report["revision"] != head:
                    self.engine.dispose()
                    migration = Config(str(resource("backend/alembic.ini")))
                    migration.attributes["database_url"] = self.settings.database_url
                    command.upgrade(migration, "head")
            except Exception as error:
                if not touched and isinstance(error, HTTPException):
                    raise
                logger.exception("Falha ao restaurar %s", name)
                if touched:
                    try:
                        self._undo(
                            self.directory(config) / safety["name"],
                            scratch,
                            staging,
                            replaced,
                            moved,
                            placed,
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
                for folder in staging.values():
                    shutil.rmtree(folder.parent, ignore_errors=True)
                self.engine.dispose()
        logger.warning("Backup restaurado: %s (cópia prévia %s)", name, safety["name"])
        aside = sorted({str(replaced[label].parent) for label in moved})
        return {
            "restored": name,
            "safety_backup": safety["name"],
            "revision": report["revision"],
            "upgraded_to": head if report["revision"] != head else None,
            "replaced_files": "; ".join(aside) or None,
        }


def describe(error: BaseException) -> str:
    """Short, path-free reason for the history; the full trace goes to the log."""
    if isinstance(error, PermissionError):
        return "Sem permissão para gravar na pasta de backups."
    if isinstance(error, FileNotFoundError):
        return "Pasta ou arquivo não encontrado (disco desconectado?)."
    if isinstance(error, OSError) and error.errno == 28:
        return "Disco cheio."
    if isinstance(error, OSError):
        return "Erro de gravação no disco: " + (error.strerror or type(error).__name__) + "."
    if isinstance(error, sqlite3.Error):
        return "Erro ao copiar o banco de dados."
    return str(error) or type(error).__name__


class BackupScheduler(threading.Thread):
    """Checks once a minute whether an automatic backup is due; never overlaps another one."""

    def __init__(self, manager: BackupManager, interval: float = 60):
        super().__init__(name="locacontrol-backup", daemon=True)
        self.manager = manager
        self.interval = interval
        self.stop_event = threading.Event()
        self.failed_at: datetime | None = None
        self.backoff = RETRY_MINUTES

    def tick(self, now: datetime | None = None) -> dict | None:
        # A restore or a manual backup in progress: skip this minute instead of queueing.
        if not OPERATION_LOCK.acquire(blocking=False):
            return None
        try:
            return self._tick(now or datetime.now(BUSINESS_TZ))
        finally:
            OPERATION_LOCK.release()

    def _tick(self, now: datetime) -> dict | None:
        manager = self.manager
        with Session(manager.engine) as db:
            config = manager.config(db)
        if not config["enabled"]:
            return None
        history = manager.history()
        unchanged = history.get("unchanged_at")
        unchanged_at = datetime.fromisoformat(unchanged) if unchanged else None
        names = [item["name"] for item in manager.listing(config)]
        if not due(config, now, names, unchanged_at):
            return None
        minutes = FREQUENCIES.get(config["frequency"])
        if self.failed_at and now - self.failed_at < timedelta(minutes=self.backoff):
            return None
        success = history.get("last_success")
        last = success and success.get("name")
        if (
            minutes
            and last in names
            and history.get("fingerprint")
            and history["fingerprint"] == manager.fingerprint()
        ):
            # Nothing changed since the last set: record the check instead of a duplicate copy.
            data = manager.history()
            data["unchanged_at"] = now.isoformat(timespec="seconds")
            try:
                manager._save_history(data)
            except OSError:
                logger.exception("Não foi possível registrar a verificação do backup.")
            return {"skipped": True, "reason": "unchanged", "last": last}
        try:
            result = manager.create(config, "auto")
        except Exception as error:
            # Recorded in the history by create(); retried in a few minutes, not every minute.
            # Lack of space is retried once an hour, so the history is not flooded.
            self.failed_at = now
            space = isinstance(error, HTTPException) and error.status_code == SPACE_STATUS
            self.backoff = (
                SPACE_RETRY_MINUTES if space else min(minutes or RETRY_MINUTES, RETRY_MINUTES)
            )
            raise
        self.failed_at = None
        return result

    def run(self):
        while not self.stop_event.wait(self.interval):
            try:
                self.tick()
            except Exception:  # noqa: BLE001 — a failed backup must not stop later attempts
                logger.exception("Falha no backup automático.")

    def stop(self):
        self.stop_event.set()
