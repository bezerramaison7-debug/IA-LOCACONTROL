import shutil
import time
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.auth.dependencies import DB, require
from app.auth.models import User
from app.auth.service import IdentityService
from app.imports.models import ImportBatch
from app.imports.schemas import Confirmation, Mapping
from app.imports.service import SCHEMAS, ImportService, batch_view, fields
from app.imports.workbook import MAX_BYTES, analysis, checksum, read_workbook

router = APIRouter(prefix="/api/imports", tags=["Importação Excel"])
Reader = Annotated[User, Depends(require("imports.read"))]
Writer = Annotated[User, Depends(require("imports.write"))]


def service(request, db, user):
    return ImportService(db, user, request.app.state.settings.import_directory)


@router.get("/fields")
def targets(user: Reader):
    return {entity: fields(entity) for entity in SCHEMAS}


@router.get("")
def batches(db: DB, user: Reader, offset: Annotated[int, Query(ge=0)] = 0):
    rows = db.scalars(
        select(ImportBatch)
        .order_by(ImportBatch.created_at.desc(), ImportBatch.id)
        .offset(offset)
        .limit(20)
    )
    return [batch_view(b) | {"report": None} for b in rows]


@router.post("/upload", status_code=201)
async def upload(request: Request, db: DB, user: Writer, file: Annotated[UploadFile, File()]):
    filename = (file.filename or "").replace("\\", "/").split("/")[-1][:255]
    if Path(filename).suffix.lower() not in {".xlsx", ".xlsm"}:
        raise HTTPException(422, "Use .xlsx ou .xlsm. Salve arquivos .xls como .xlsx no Excel.")
    data = await file.read(MAX_BYTES + 1)
    await file.close()
    sheets = read_workbook(data)
    batch = ImportBatch(
        id=uuid4().hex,
        filename=filename,
        checksum=checksum(data),
        created_at=int(time.time()),
        created_by=user.id,
        status="UPLOADED",
        total_rows=0,
        successful_rows=0,
        warning_rows=0,
        failed_rows=0,
        ignored_rows=0,
    )
    directory = request.app.state.settings.import_directory
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (batch.id + ".xlsx")
    # Generated name only; the uploaded filename is never used as a filesystem path.
    try:
        with path.open("xb") as target:
            target.write(data)
        db.add(batch)
        db.flush()
        IdentityService(db, user).audit(
            "imports.upload",
            "ImportBatch",
            batch.id,
            {"filename": filename, "checksum": batch.checksum},
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"batch": batch_view(batch), "sheets": analysis(sheets)}


@router.get("/{batch_id}")
def details(batch_id: str, request: Request, db: DB, user: Reader):
    importer = service(request, db, user)
    batch = importer.batch(batch_id)
    return {"batch": batch_view(batch), "sheets": analysis(importer.read(batch))}


@router.post("/{batch_id}/new-conversion", status_code=201)
def new_conversion(batch_id: str, request: Request, db: DB, user: Writer):
    importer = service(request, db, user)
    source = importer.batch(batch_id)
    sheets = importer.read(source)
    batch = ImportBatch(
        id=uuid4().hex,
        filename=source.filename,
        checksum=source.checksum,
        created_at=int(time.time()),
        created_by=user.id,
        status="UPLOADED",
        total_rows=0,
        successful_rows=0,
        warning_rows=0,
        failed_rows=0,
        ignored_rows=0,
    )
    destination = importer.directory / (batch.id + ".xlsx")
    try:
        shutil.copyfile(importer.directory / (source.id + ".xlsx"), destination)
        db.add(batch)
        db.flush()
        IdentityService(db, user).audit(
            "imports.new_conversion", "ImportBatch", batch.id, {"source_batch": source.id}
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return {"batch": batch_view(batch), "sheets": analysis(sheets)}


@router.get("/{batch_id}/original")
def original(batch_id: str, request: Request, db: DB, user: Reader):
    importer = service(request, db, user)
    batch = importer.batch(batch_id)
    importer.read(batch)  # Verify preserved checksum before serving.
    return FileResponse(
        importer.directory / (batch.id + ".xlsx"),
        filename=batch.filename,
        media_type="application/octet-stream",
    )


@router.post("/{batch_id}/preview")
def preview(batch_id: str, payload: Mapping, request: Request, db: DB, user: Writer):
    importer = service(request, db, user)
    return importer.process(importer.batch(batch_id), payload)


@router.post("/{batch_id}/confirm")
def confirm(batch_id: str, payload: Confirmation, request: Request, db: DB, user: Writer):
    importer = service(request, db, user)
    return importer.confirm(importer.batch(batch_id), payload)


@router.get("/{batch_id}/report")
def report(batch_id: str, request: Request, db: DB, user: Reader):
    batch = service(request, db, user).batch(batch_id)
    if batch.report is None:
        raise HTTPException(409, "Importação ainda não confirmada.")
    return batch.report
