from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from app.auth.dependencies import DB, require
from app.auth.models import User
from app.contracts import schemas as s
from app.contracts.documents import DocumentService
from app.contracts.operations import OperationService
from app.contracts.service import ContractService, page

router = APIRouter(prefix="/api/contracts", tags=["Contratos"])
Read = Annotated[User, Depends(require("contracts.read"))]
Write = Annotated[User, Depends(require("contracts.write"))]
Configure = Annotated[User, Depends(require("contracts.configure"))]
Operate = Annotated[User, Depends(require("operations.write"))]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=160)]


def soon(request: Request) -> int:
    return request.app.state.settings.contract_due_soon_days


def contracts(request: Request, db, user) -> ContractService:
    return ContractService(db, user, soon(request))


def operations(request: Request, db, user) -> OperationService:
    return OperationService(db, user, soon(request))


def documents(request: Request, db, user) -> DocumentService:
    return DocumentService(db, user, request.app.state.settings)


def pdf_response(content: bytes, filename: str) -> Response:
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("")
def listing(
    request: Request,
    db: DB,
    user: Read,
    q: Search = "",
    status: s.Status | None = None,
    customer_id: int | None = None,
    offset: Offset = 0,
    limit: Limit = 20,
):
    return page(
        db, soon(request), q=q, status=status, customer_id=customer_id, offset=offset, limit=limit
    )


@router.get("/numbering")
def numbering(request: Request, db: DB, user: Read):
    return contracts(request, db, user).numbering()


@router.put("/numbering")
def set_numbering(request: Request, payload: s.NumberingInput, db: DB, user: Configure):
    return contracts(request, db, user).set_numbering(payload)


@router.get("/templates")
def templates(request: Request, db: DB, user: Read):
    return documents(request, db, user).templates()


@router.post("/templates", status_code=201)
def publish_template(request: Request, payload: s.TemplateInput, db: DB, user: Configure):
    return documents(request, db, user).save_template(payload)


@router.post("/from-quote/{quote_id}", status_code=201)
def from_quote(request: Request, quote_id: int, payload: s.ActionInput, db: DB, user: Write):
    return contracts(request, db, user).from_quote(quote_id, payload)


@router.get("/documents/{document_id}/download")
def download_document(request: Request, document_id: int, db: DB, user: Read):
    return pdf_response(*documents(request, db, user).download(document_id))


@router.post("/documents/{document_id}/sign")
def sign_document(request: Request, document_id: int, payload: s.SignInput, db: DB, user: Write):
    return documents(request, db, user).sign(document_id, payload)


@router.post("", status_code=201)
def create(request: Request, payload: s.ContractInput, db: DB, user: Write):
    return contracts(request, db, user).save(payload)


@router.get("/{record_id}")
def detail(request: Request, record_id: int, db: DB, user: Read):
    return contracts(request, db, user).detail(record_id)


@router.put("/{record_id}")
def update(request: Request, record_id: int, payload: s.ContractUpdate, db: DB, user: Write):
    return contracts(request, db, user).save(payload, record_id)


@router.post("/{record_id}/confirm")
def confirm(request: Request, record_id: int, payload: s.ActionInput, db: DB, user: Write):
    return contracts(request, db, user).confirm(record_id, payload)


@router.post("/{record_id}/cancel")
def cancel(request: Request, record_id: int, payload: s.ActionInput, db: DB, user: Write):
    return contracts(request, db, user).cancel(record_id, payload)


@router.post("/{record_id}/close")
def close(request: Request, record_id: int, payload: s.ActionInput, db: DB, user: Write):
    return contracts(request, db, user).close(record_id, payload)


@router.post("/{record_id}/renew", status_code=201)
def renew(request: Request, record_id: int, payload: s.RenewInput, db: DB, user: Write):
    return operations(request, db, user).renew(record_id, payload)


@router.post("/{record_id}/withdrawals", status_code=201)
def withdraw(request: Request, record_id: int, payload: s.WithdrawInput, db: DB, user: Operate):
    return operations(request, db, user).withdraw(record_id, payload)


@router.post("/{record_id}/returns", status_code=201)
def give_back(request: Request, record_id: int, payload: s.ReturnInput, db: DB, user: Operate):
    return operations(request, db, user).give_back(record_id, payload)


@router.get("/{record_id}/preview.pdf")
def preview(request: Request, record_id: int, db: DB, user: Read):
    return pdf_response(*documents(request, db, user).preview(record_id))


@router.post("/{record_id}/documents", status_code=201)
def generate_document(
    request: Request, record_id: int, payload: s.GenerateInput, db: DB, user: Write
):
    return documents(request, db, user).generate(record_id, payload)
