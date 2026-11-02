from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from app.auth.dependencies import DB, require
from app.auth.models import User
from app.masters.schemas import Period
from app.quotes import schemas as s
from app.quotes.pdf import quote_pdf
from app.quotes.service import QuoteService, page

router = APIRouter(prefix="/api/quotes", tags=["Orçamentos"])
QuotesRead = Annotated[User, Depends(require("quotes.read"))]
QuotesWrite = Annotated[User, Depends(require("quotes.write"))]
QuotesApprove = Annotated[User, Depends(require("quotes.approve"))]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=160)]


@router.get("")
def quotes(
    db: DB,
    user: QuotesRead,
    q: Search = "",
    status: s.Status | None = None,
    customer_id: int | None = None,
    offset: Offset = 0,
    limit: Limit = 20,
):
    return page(db, q=q, status=status, customer_id=customer_id, offset=offset, limit=limit)


@router.get("/pricing")
def pricing(product_id: int, period: Period, at: date, db: DB, user: QuotesRead):
    return QuoteService(db, user).pricing(product_id, period, at)


@router.get("/{record_id}")
def quote(record_id: int, db: DB, user: QuotesRead):
    return QuoteService(db, user).detail(record_id)


@router.get("/{record_id}/pdf")
def pdf(record_id: int, request: Request, db: DB, user: QuotesRead):
    data = QuoteService(db, user).detail(record_id)
    return Response(
        quote_pdf(data, request.app.state.settings),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{data["number"]}.pdf"'},
    )


@router.post("", status_code=201)
def create_quote(payload: s.QuoteInput, db: DB, user: QuotesWrite):
    return QuoteService(db, user).save(payload)


@router.put("/{record_id}")
def update_quote(record_id: int, payload: s.QuoteUpdate, db: DB, user: QuotesWrite):
    return QuoteService(db, user).save(payload, record_id)


@router.post("/{record_id}/duplicate", status_code=201)
def duplicate_quote(record_id: int, payload: s.DuplicateInput, db: DB, user: QuotesWrite):
    return QuoteService(db, user).duplicate(record_id, payload)


@router.post("/{record_id}/send")
def send_quote(record_id: int, payload: s.TransitionInput, db: DB, user: QuotesWrite):
    return QuoteService(db, user).transition(record_id, "send", payload)


@router.post("/{record_id}/approve")
def approve_quote(record_id: int, payload: s.TransitionInput, db: DB, user: QuotesApprove):
    return QuoteService(db, user).transition(record_id, "approve", payload)


@router.post("/{record_id}/reject")
def reject_quote(record_id: int, payload: s.TransitionInput, db: DB, user: QuotesWrite):
    return QuoteService(db, user).transition(record_id, "reject", payload)


@router.post("/{record_id}/cancel")
def cancel_quote(record_id: int, payload: s.TransitionInput, db: DB, user: QuotesWrite):
    return QuoteService(db, user).transition(record_id, "cancel", payload)


@router.post("/{record_id}/reopen")
def reopen_quote(record_id: int, payload: s.TransitionInput, db: DB, user: QuotesWrite):
    return QuoteService(db, user).transition(record_id, "reopen", payload)
