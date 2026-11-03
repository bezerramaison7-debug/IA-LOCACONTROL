import secrets
import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.catalog import permission_codes
from app.auth.models import AuthSession, User
from app.auth.security import COOKIE, csrf_token, digest
from app.network.stations import (
    NOT_PAIRED,
    STATION_COOKIE,
    from_store_network,
    peer_address,
    same_origin,
)


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
    settings = request.app.state.settings
    origin = request.headers.get("origin")
    # A station's page comes from the address it used to reach this server (ADR-025).
    lan = settings.local_mode and settings.network_mode and same_origin(request)
    if (origin not in settings.allowed_origins and not lan) or request.headers.get(
        "x-locacontrol-request"
    ) != "1":
        raise HTTPException(403, "Origem da solicitação não permitida.")


def bound_station(request: Request, session: AuthSession) -> dict | None:
    """Local edition: who the session belongs to must still be true at every request.

    A station session needs its own valid, unrevoked station cookie and a store-network peer;
    a session of this computer, with the network open, needs a loopback peer.
    """
    settings = request.app.state.settings
    if not settings.local_mode:
        return None
    if session.station_id:
        peer = peer_address(request)
        station = request.app.state.stations.authenticate(
            request.cookies.get(STATION_COOKIE), str(peer) if peer else None
        )
        if not station or station["id"] != session.station_id or not from_store_network(request):
            raise HTTPException(401, NOT_PAIRED)
        return station
    if settings.network_mode:
        peer = peer_address(request)
        if peer is None or not peer.is_loopback:
            raise HTTPException(401, NOT_PAIRED)
    return None


def current_user(request: Request, db: DB) -> User:
    token = request.cookies.get(COOKIE, "")
    session = db.get(AuthSession, digest(token)) if token and len(token) <= 100 else None
    if not session or session.expires_at <= int(time.time()):
        raise HTTPException(401, "Sua sessão expirou. Entre novamente.")
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Sua sessão expirou. Entre novamente.")
    station = bound_station(request, session)
    # Read by the audit label, the draft owner and the "main computer only" guard.
    request.state.station = station
    db.info["station"] = station
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
