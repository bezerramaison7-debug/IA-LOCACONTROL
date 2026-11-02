from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from app.auth.dependencies import DB, require
from app.auth.models import User
from app.fiscal.provider import build_provider
from app.fiscal.service import FiscalAction, FiscalInput, FiscalService, page

router = APIRouter(prefix="/api/fiscal", tags=["Faturamento e fiscal"])
Read = Annotated[User, Depends(require("fiscal.read"))]
Write = Annotated[User, Depends(require("fiscal.write"))]
Status = Literal["PENDENTE", "PROCESSANDO", "EMITIDO", "ERRO", "CANCELADO"]


def service(request: Request, db, user) -> FiscalService:
    return FiscalService(db, user, request.app.state.settings)


@router.get("/provider")
def provider(request: Request, user: Read):
    current = build_provider(request.app.state.settings)
    return {
        "name": current.name,
        "environment": current.environment,
        "is_simulation": current.environment == "SIMULACAO",
        "document_kind": request.app.state.settings.fiscal_document_kind,
    }


@router.get("/documents")
def documents(
    db: DB,
    user: Read,
    status: Status | None = None,
    customer_id: int | None = None,
    contract_id: int | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return page(db, status, customer_id, contract_id, offset, limit)


@router.post("/documents", status_code=201)
def create(request: Request, payload: FiscalInput, db: DB, user: Write):
    return service(request, db, user).create(payload)


@router.get("/documents/{record_id}")
def detail(request: Request, record_id: int, db: DB, user: Read):
    return service(request, db, user).detail(record_id)


@router.post("/documents/{record_id}/emit")
def emit(request: Request, record_id: int, payload: FiscalAction, db: DB, user: Write):
    return service(request, db, user).emit(record_id, payload)


@router.post("/documents/{record_id}/refresh")
def refresh(request: Request, record_id: int, payload: FiscalAction, db: DB, user: Write):
    return service(request, db, user).refresh(record_id, payload)


@router.post("/documents/{record_id}/cancel")
def cancel(request: Request, record_id: int, payload: FiscalAction, db: DB, user: Write):
    return service(request, db, user).cancel(record_id, payload)


@router.get("/documents/{record_id}/{kind}")
def download(request: Request, record_id: int, kind: Literal["pdf", "xml"], db: DB, user: Read):
    content, filename, media = service(request, db, user).file(record_id, kind)
    return Response(
        content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
