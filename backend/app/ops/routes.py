import time
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import DB, require
from app.auth.models import AuditLog, User
from app.auth.security import verify_password
from app.auth.service import IdentityService
from app.contracts.models import AppSetting
from app.masters.schemas import Input
from app.network.stations import principal_only
from app.ops.backup import SETTING_KEY, BackupManager

router = APIRouter(prefix="/api/backups", tags=["Backup e restauração"])
Manage = Annotated[User, Depends(require("backups.manage"))]
# Restore, configuration, download and import: the main computer only (ADR-025).
Principal = Annotated[None, Depends(principal_only)]


class BackupConfig(Input):
    enabled: bool
    # Every 20 minutes (default), every 60 minutes, or once a day at `time` (ADR-024).
    frequency: Literal["20min", "60min", "daily"] = "20min"
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    # Days with a kept copy; every set of the last 24 hours is kept besides these.
    keep: int = Field(ge=1, le=365)
    # Empty keeps the default folder inside the installation.
    directory: str = Field(default="", max_length=260)
    # Optional second copy of each set, ideally on another disk; empty turns it off.
    mirror_directory: str = Field(default="", max_length=260)
    # Storage limits (A3): cap of the backup folder; free space kept on its disk, the larger of
    # the absolute and the relative floor.
    max_total_gb: int = Field(default=10, ge=1, le=100_000)
    min_free_gb: int = Field(default=10, ge=0, le=100_000)
    # Operational margin on top of the minimum reserve (P1-E): this % of the disk, at most
    # margin_max_gb, never less than twice the database.
    margin_percent: int = Field(default=5, ge=0, le=50)
    margin_max_gb: int = Field(default=20, ge=0, le=100_000)

    @field_validator("directory", "mirror_directory")
    @classmethod
    def absolute_directory(cls, value):
        if value and not Path(value).is_absolute():
            raise ValueError("Informe o caminho completo da pasta")
        return value


class RestoreInput(Input):
    # Must be exactly "RESTAURAR <nome do backup>".
    confirmation: str = Field(max_length=120)
    # Required in the login-based edition; the local edition has no application password.
    password: str | None = Field(default=None, min_length=1, max_length=200)


def manager(request: Request) -> BackupManager:
    return BackupManager(request.app.state.settings, request.app.state.engine)


def state(backups: BackupManager, db) -> dict:
    config = backups.config(db)
    items = backups.listing(config)
    return {
        "config": config,
        "directory": str(backups.directory(config)),
        "items": items,
        "total_size": sum(item["size"] for item in items),
        "status": backups.status(config),
    }


@router.get("")
def overview(request: Request, db: DB, user: Manage):
    return state(manager(request), db)


@router.get("/status")
def status(request: Request, db: DB, user: Manage):
    """Summary for the dashboard warning: last copy, last failure and the alert to show."""
    backups = manager(request)
    return backups.status(backups.config(db))


@router.put("/config")
def configure(request: Request, payload: BackupConfig, db: DB, user: Manage, _: Principal):
    backups = manager(request)
    before = backups.config(db)
    values = payload.model_dump()
    try:
        backups.directory(values).mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise HTTPException(422, "Não foi possível usar a pasta informada.") from error
    if values["mirror_directory"]:
        mirror = Path(values["mirror_directory"])
        if mirror.resolve() == backups.directory(values).resolve():
            raise HTTPException(422, "A segunda cópia precisa ficar em outra pasta.")
        try:
            mirror.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise HTTPException(
                422,
                "Não foi possível usar a pasta da segunda cópia. Confira se o disco está "
                "conectado.",
            ) from error
    row = db.get(AppSetting, SETTING_KEY)
    if row is None:
        row = AppSetting(key=SETTING_KEY, value={})
        db.add(row)
    row.value = values
    row.updated_at = int(time.time())
    row.updated_by = user.id
    IdentityService(db, user).audit(
        "backup.configured", "app_settings", SETTING_KEY, {"before": before, "after": values}
    )
    db.flush()
    return state(backups, db)


@router.post("", status_code=201)
def run_now(request: Request, db: DB, user: Manage):
    backups = manager(request)
    config = backups.config(db)
    IdentityService(db, user).audit("backup.requested", "backups", None, {})
    # Commit first: the backup reads the database through its own connection.
    db.commit()
    return backups.create(config, "manual")


@router.post("/import", status_code=201)
async def import_set(
    request: Request, db: DB, user: Manage, _: Principal, file: Annotated[UploadFile, File()]
):
    """Brings a set kept on another disk into the backup folder, verified, ready to restore."""
    backups = manager(request)
    config = backups.config(db)
    filename = (file.filename or "").replace("\\", "/").split("/")[-1][:255]
    if not filename.lower().endswith(".zip"):
        raise HTTPException(422, "Escolha o arquivo .zip de um backup do LocaControl.")
    # Release the writer lock: copying and verifying a large set must not block the store.
    db.commit()
    try:
        result = await run_in_threadpool(backups.import_set, config, file.file, filename)
    finally:
        await file.close()
    IdentityService(db, user).audit(
        "backup.imported",
        "backups",
        result["name"],
        {"original_name": filename, "size": result["size"], "revision": result["revision"]},
    )
    return result


@router.post("/{name}/verify")
def verify(request: Request, name: str, db: DB, user: Manage):
    backups = manager(request)
    return backups.verify(backups.path(backups.config(db), name))


@router.get("/{name}/download")
def download(request: Request, name: str, db: DB, user: Manage, _: Principal):
    backups = manager(request)
    path = backups.path(backups.config(db), name)
    return FileResponse(path, media_type="application/zip", filename=name)


@router.post("/{name}/restore")
def restore(request: Request, name: str, payload: RestoreInput, db: DB, user: Manage, _: Principal):
    backups = manager(request)
    config = backups.config(db)
    backups.path(config, name)
    if payload.confirmation != f"RESTAURAR {name}":
        raise HTTPException(422, f'Digite exatamente "RESTAURAR {name}" para confirmar.')
    service = IdentityService(db, user)
    label = service.label()
    # Local edition (ADR-023): no password; the phrase, maintenance mode and the copy remain.
    if not request.app.state.settings.local_mode:
        if payload.password is None:
            raise HTTPException(422, "Dados inválidos. Confira os campos e os limites informados.")
        if not verify_password(user.password_hash, payload.password):
            service.audit("backup.restore_denied", "backups", name, {})
            db.commit()
            raise HTTPException(403, "Senha incorreta. A restauração não foi executada.")
    # The restore replaces the database contents: release this request's writer lock first.
    db.commit()
    db.close()
    # Maintenance: new requests get 503 and this waits for the ones in flight (held=1 is this one).
    with request.app.state.gate.exclusive(held=1):
        result = backups.restore(config, name)
        with Session(request.app.state.engine) as restored:
            # The acting account may not exist in the restored data; keep only its label.
            restored.add(
                AuditLog(
                    actor_id=None,
                    actor_label=label,
                    action="backup.restored",
                    entity="backups",
                    entity_id=name,
                    changes=result,
                )
            )
            restored.commit()
    local = request.app.state.settings.local_mode
    return {
        **result,
        "message": "Backup restaurado."
        if local
        else "Backup restaurado. Entre novamente: as sessões voltaram ao estado do backup.",
    }
