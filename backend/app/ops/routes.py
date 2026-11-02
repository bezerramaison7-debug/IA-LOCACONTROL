import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import DB, require
from app.auth.models import AuditLog, User
from app.auth.security import verify_password
from app.auth.service import IdentityService
from app.contracts.models import AppSetting
from app.masters.schemas import Input
from app.ops.backup import SETTING_KEY, BackupManager

router = APIRouter(prefix="/api/backups", tags=["Backup e restauração"])
Manage = Annotated[User, Depends(require("backups.manage"))]


class BackupConfig(Input):
    enabled: bool
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    keep: int = Field(ge=1, le=365)
    # Empty keeps the default folder inside the installation.
    directory: str = Field(default="", max_length=260)

    @field_validator("directory")
    @classmethod
    def absolute_directory(cls, value):
        if value and not Path(value).is_absolute():
            raise ValueError("Informe o caminho completo da pasta")
        return value


class RestoreInput(Input):
    # Must be exactly "RESTAURAR <nome do backup>".
    confirmation: str = Field(max_length=120)
    password: str = Field(min_length=1, max_length=200)


def manager(request: Request) -> BackupManager:
    return BackupManager(request.app.state.settings, request.app.state.engine)


def state(backups: BackupManager, db) -> dict:
    config = backups.config(db)
    return {
        "config": config,
        "directory": str(backups.directory(config)),
        "items": backups.listing(config),
    }


@router.get("")
def overview(request: Request, db: DB, user: Manage):
    return state(manager(request), db)


@router.put("/config")
def configure(request: Request, payload: BackupConfig, db: DB, user: Manage):
    backups = manager(request)
    before = backups.config(db)
    values = payload.model_dump()
    try:
        backups.directory(values).mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise HTTPException(422, "Não foi possível usar a pasta informada.") from error
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


@router.post("/{name}/verify")
def verify(request: Request, name: str, db: DB, user: Manage):
    backups = manager(request)
    return backups.verify(backups.path(backups.config(db), name))


@router.get("/{name}/download")
def download(request: Request, name: str, db: DB, user: Manage):
    backups = manager(request)
    path = backups.path(backups.config(db), name)
    return FileResponse(path, media_type="application/zip", filename=name)


@router.post("/{name}/restore")
def restore(request: Request, name: str, payload: RestoreInput, db: DB, user: Manage):
    backups = manager(request)
    config = backups.config(db)
    backups.path(config, name)
    if payload.confirmation != f"RESTAURAR {name}":
        raise HTTPException(422, f'Digite exatamente "RESTAURAR {name}" para confirmar.')
    username = user.username
    if not verify_password(user.password_hash, payload.password):
        IdentityService(db, user).audit("backup.restore_denied", "backups", name, {})
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
                    actor_label=username,
                    action="backup.restored",
                    entity="backups",
                    entity_id=name,
                    changes=result,
                )
            )
            restored.commit()
    return {
        **result,
        "message": "Backup restaurado. Entre novamente: as sessões voltaram ao estado do backup.",
    }
