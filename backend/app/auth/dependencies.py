import secrets
import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.catalog import permission_codes
from app.auth.models import AuthSession, User
from app.auth.security import COOKIE, csrf_token, digest


def database(request: Request):
    with Session(request.app.state.engine, expire_on_commit=False) as db:
        try:
            # SQLite writer lock prevents concurrent bootstrap/last-admin races.
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                db.execute(text("BEGIN IMMEDIATE"))
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


DB = Annotated[Session, Depends(database, scope="function")]


def trusted_request(request: Request):
    if (
        request.headers.get("origin") not in request.app.state.settings.allowed_origins
        or request.headers.get("x-locacontrol-request") != "1"
    ):
        raise HTTPException(403, "Origem da solicitação não permitida.")


def current_user(request: Request, db: DB) -> User:
    token = request.cookies.get(COOKIE, "")
    session = db.get(AuthSession, digest(token)) if token and len(token) <= 100 else None
    if not session or session.expires_at <= int(time.time()):
        raise HTTPException(401, "Sua sessão expirou. Entre novamente.")
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Sua sessão expirou. Entre novamente.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        trusted_request(request)
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), csrf_token(token)):
            # The header lets the interface fetch the current token without losing the form.
            raise HTTPException(
                403,
                "Solicitação inválida. Atualize a página e tente novamente.",
                headers={"X-LocaControl-Retry": "csrf"},
            )
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require(permission: str):
    def check(user: CurrentUser):
        if user.must_change_password:
            raise HTTPException(403, "Altere sua senha antes de continuar.")
        if permission not in permission_codes(user):
            raise HTTPException(403, "Você não tem permissão para esta ação.")
        return user

    return check
