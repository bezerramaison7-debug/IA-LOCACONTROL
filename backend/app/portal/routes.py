from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from app.auth.dependencies import DB, require
from app.auth.models import User
from app.contracts.schemas import Status
from app.portal.service import (
    DecisionInput,
    LinkInput,
    PortalAdmin,
    PortalService,
    RenewalRequestInput,
)

router = APIRouter(prefix="/api", tags=["Portal do cliente"])
PortalUser = Annotated[User, Depends(require("portal.access"))]
UsersRead = Annotated[User, Depends(require("users.read"))]
UsersWrite = Annotated[User, Depends(require("users.write"))]
ContractsRead = Annotated[User, Depends(require("contracts.read"))]
ContractsWrite = Annotated[User, Depends(require("contracts.write"))]
RequestStatus = Literal["PENDENTE", "APROVADA", "RECUSADA", "CANCELADA"]


def portal(request: Request, db, user) -> PortalService:
    return PortalService(db, user, request.app.state.settings)


def pdf(content: bytes, filename: str) -> Response:
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/portal/dashboard")
def dashboard(request: Request, db: DB, user: PortalUser):
    return portal(request, db, user).dashboard()


@router.get("/portal/contracts")
def contracts(request: Request, db: DB, user: PortalUser, status: Status | None = None):
    return portal(request, db, user).contract_list(status)


@router.get("/portal/contracts/{contract_id}")
def contract(request: Request, contract_id: int, db: DB, user: PortalUser):
    return portal(request, db, user).contract_detail(contract_id)


@router.get("/portal/equipment")
def equipment(request: Request, db: DB, user: PortalUser):
    return portal(request, db, user).equipment()


@router.get("/portal/documents")
def documents(request: Request, db: DB, user: PortalUser):
    return portal(request, db, user).documents()


@router.get("/portal/documents/{document_id}/download")
def download(request: Request, document_id: int, db: DB, user: PortalUser):
    return pdf(*portal(request, db, user).download(document_id))


@router.get("/portal/quotes")
def quotes(request: Request, db: DB, user: PortalUser):
    return portal(request, db, user).quotes()


@router.get("/portal/quotes/{quote_id}")
def quote(request: Request, quote_id: int, db: DB, user: PortalUser):
    return portal(request, db, user).quote_detail(quote_id)


@router.get("/portal/quotes/{quote_id}/pdf")
def quote_document(request: Request, quote_id: int, db: DB, user: PortalUser):
    return pdf(*portal(request, db, user).quote_pdf(quote_id))


@router.get("/portal/profile")
def profile(request: Request, db: DB, user: PortalUser):
    return portal(request, db, user).profile()


@router.get("/portal/renewal-requests")
def my_requests(request: Request, db: DB, user: PortalUser):
    return portal(request, db, user).requests()


@router.post("/portal/renewal-requests", status_code=201)
def request_renewal(request: Request, payload: RenewalRequestInput, db: DB, user: PortalUser):
    return portal(request, db, user).request_renewal(payload)


@router.post("/portal/renewal-requests/{request_id}/cancel")
def cancel_request(request: Request, request_id: int, db: DB, user: PortalUser):
    return portal(request, db, user).cancel_request(request_id)


@router.get("/users/{user_id}/customer")
def user_customer(user_id: int, db: DB, user: UsersRead):
    return PortalAdmin(db, user).link_view(user_id)


@router.put("/users/{user_id}/customer")
def link_customer(user_id: int, payload: LinkInput, db: DB, user: UsersWrite):
    return PortalAdmin(db, user).link(user_id, payload)


@router.get("/renewal-requests")
def renewal_requests(
    db: DB,
    user: ContractsRead,
    status: RequestStatus | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return PortalAdmin(db, user).requests(status, offset, limit)


@router.post("/renewal-requests/{request_id}/decide")
def decide(request_id: int, payload: DecisionInput, db: DB, user: ContractsWrite):
    return PortalAdmin(db, user).decide(request_id, payload)
