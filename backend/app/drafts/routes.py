"""Draft API: save (replace), read back, list and discard the caller's own drafts.

Saving is a full replacement keyed by (owner, kind, scope), so repeating it is harmless; that
is why the interface may save again after a failure. Drafts are not audited: they are not
operations, and the audit records each definitive operation when it happens.
"""

import json
import time
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Request, Response
from pydantic import Field
from sqlalchemy import delete, select

from app.auth.catalog import permission_codes
from app.auth.dependencies import DB, CurrentUser
from app.auth.models import User
from app.drafts.models import FormDraft
from app.masters.schemas import Input

router = APIRouter(prefix="/api/drafts", tags=["Rascunhos"])

# A draft expires this long after its last change (decision of the user, 2026-11-02).
TTL_SECONDS = 7 * 24 * 3600
MAX_PAYLOAD_BYTES = 200_000
# The permission of the definitive operation: no draft for what the user cannot do.
KINDS = {
    "quote": "quotes.write",
    "contract": "contracts.write",
    "withdrawal": "operations.write",
    "return": "operations.write",
    "renewal": "contracts.write",
}
Kind = Literal["quote", "contract", "withdrawal", "return", "renewal"]
Scope = Annotated[str, Path(pattern=r"^(new|\d{1,12})$")]


class DraftInput(Input):
    payload: dict
    base_version: int | None = Field(default=None, ge=0)


def owner(request: Request, user: User) -> str:
    """Drafts belong to whoever typed them. The network edition adds the station."""
    return f"user:{user.id}"


def allowed(user: User, kind: str):
    if KINDS[kind] not in permission_codes(user):
        raise HTTPException(403, "Você não tem permissão para esta ação.")


def purge(db):
    db.execute(delete(FormDraft).where(FormDraft.expires_at <= int(time.time())))


def view(draft: FormDraft) -> dict:
    return {
        "kind": draft.kind,
        "scope": draft.scope,
        "payload": draft.payload,
        "base_version": draft.base_version,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
        "expires_at": draft.expires_at,
    }


def find(db, request, user, kind, scope) -> FormDraft | None:
    return db.scalar(
        select(FormDraft).where(
            FormDraft.owner == owner(request, user),
            FormDraft.kind == kind,
            FormDraft.scope == scope,
        )
    )


@router.get("")
def mine(request: Request, db: DB, user: CurrentUser):
    now = int(time.time())
    drafts = db.scalars(
        select(FormDraft)
        .where(FormDraft.owner == owner(request, user), FormDraft.expires_at > now)
        .order_by(FormDraft.updated_at.desc())
    )
    return {
        "items": [
            {k: v for k, v in view(d).items() if k != "payload"}
            for d in drafts
            if KINDS[d.kind] in permission_codes(user)
        ],
        "ttl_days": TTL_SECONDS // 86400,
    }


@router.get("/{kind}/{scope}")
def read(request: Request, kind: Kind, scope: Scope, db: DB, user: CurrentUser):
    allowed(user, kind)
    draft = find(db, request, user, kind, scope)
    if draft is None or draft.expires_at <= int(time.time()):
        return {"draft": None}
    return {"draft": view(draft)}


@router.put("/{kind}/{scope}")
def save(
    request: Request, kind: Kind, scope: Scope, payload: DraftInput, db: DB, user: CurrentUser
):
    allowed(user, kind)
    size = len(json.dumps(payload.payload, ensure_ascii=False).encode())
    if size > MAX_PAYLOAD_BYTES:
        raise HTTPException(413, "Rascunho grande demais para ser guardado.")
    purge(db)
    now = int(time.time())
    draft = find(db, request, user, kind, scope)
    if draft is None:
        draft = FormDraft(owner=owner(request, user), kind=kind, scope=scope, created_at=now)
        db.add(draft)
    draft.payload = payload.payload
    draft.base_version = payload.base_version
    draft.updated_at = now
    draft.expires_at = now + TTL_SECONDS
    db.flush()
    return {"draft": view(draft)}


@router.delete("/{kind}/{scope}", status_code=204)
def discard(request: Request, kind: Kind, scope: Scope, db: DB, user: CurrentUser):
    allowed(user, kind)
    db.execute(
        delete(FormDraft).where(
            FormDraft.owner == owner(request, user),
            FormDraft.kind == kind,
            FormDraft.scope == scope,
        )
    )
    return Response(status_code=204)
