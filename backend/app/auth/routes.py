import secrets
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, func, select, text

from app.auth import schemas
from app.auth.dependencies import DB, CurrentUser, current_user, require, trusted_request
from app.auth.local import (
    HIDDEN_PERMISSION_GROUPS,
    installation,
    is_this_computer,
    local_operator,
    not_in_local_mode,
)
from app.auth.models import AuditLog, AuthSession, Permission, Role, User
from app.auth.security import COOKIE, csrf_token, digest
from app.auth.service import IdentityService, user_view
from app.network.stations import (
    NOT_PAIRED,
    STATION_COOKIE,
    STATION_COOKIE_DAYS,
    from_store_network,
    peer_address,
    station_request,
    store_host,
)

router = APIRouter(prefix="/api", tags=["Identidade e segurança"])
# Login, passwords, users and roles do not exist in the local edition (ADR-023).
LoginEditionOnly = Depends(not_in_local_mode)


def secure_cookie(settings, request: Request | None) -> bool:
    """Secure when configured or when the request itself came over HTTPS (stations, P1-E)."""
    return settings.cookie_secure or bool(request and request.url.scheme == "https")


def set_session_cookie(response: Response, settings, token: str, request: Request | None = None):
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=secure_cookie(settings, request),
        samesite="strict",
        max_age=settings.session_hours * 3600,
        path="/api",
    )


@router.post("/auth/login", dependencies=[LoginEditionOnly, Depends(trusted_request)])
def login(payload: schemas.Login, request: Request, response: Response, db: DB):
    settings = request.app.state.settings
    token, result = IdentityService(db).login(
        payload.username,
        payload.password,
        request.client.host if request.client else "local",
        settings.session_hours,
    )
    old = request.cookies.get(COOKIE)
    if old:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == digest(old)))
    set_session_cookie(response, settings, token, request)
    return result


def open_local_session(
    request: Request, response: Response, db, station: dict | None = None
) -> tuple[str, User]:
    """Local edition: a session of the local operator for this computer or a paired station."""
    settings = request.app.state.settings
    # GET has no writer lock by default; take it so two first tabs do not race.
    db.execute(text("BEGIN IMMEDIATE"))
    user = local_operator(db)
    now = int(time.time())
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=digest(token),
            user_id=user.id,
            created_at=now,
            expires_at=now + settings.session_hours * 3600,
            station_id=station["id"] if station else None,
        )
    )
    db.info["station"] = station
    request.state.station = station
    IdentityService(db, user).audit(
        "local_session.opened", "users", user.id, {"station_id": station["id"]} if station else {}
    )
    set_session_cookie(response, settings, token, request)
    return token, user


def set_station_cookie(response: Response, settings, token: str, request: Request | None = None):
    response.set_cookie(
        STATION_COOKIE,
        token,
        httponly=True,
        secure=secure_cookie(settings, request),
        samesite="strict",
        max_age=STATION_COOKIE_DAYS * 86400,
        path="/api",
    )


@router.get("/auth/me")
def me(request: Request, response: Response, db: DB):
    local = request.app.state.settings.local_mode
    try:
        user = current_user(request, db)
        token = request.cookies[COOKIE]
    except HTTPException as error:
        if not local:
            raise
        station = None
        if not is_this_computer(request):
            peer = peer_address(request)
            station = None
            if station_request(request):
                # A new session always offers a new station token (A1).
                check = request.app.state.stations.authenticate(
                    request.cookies.get(STATION_COOKIE),
                    str(peer) if peer else None,
                    request.headers.get("user-agent", ""),
                    rotate_now=True,
                )
                station = check.station
                request.state.station_rotate = check.rotate
                request.state.station_reuse = check.reuse
            if not station:
                # Tells a computer of the store network that it can be paired (ADR-025).
                pairable = from_store_network(request) and store_host(request)
                raise HTTPException(
                    401,
                    NOT_PAIRED,
                    headers={"X-LocaControl-Pairing": "available"} if pairable else None,
                ) from error
        token, user = open_local_session(request, response, db, station or None)
    view = user_view(user)
    if local:
        view["permissions"] = [
            p for p in view["permissions"] if p.split(".")[0] not in HIDDEN_PERMISSION_GROUPS
        ]
    settings = request.app.state.settings
    station = getattr(request.state, "station", None)
    result = {
        "user": view,
        "csrf_token": csrf_token(token),
        "edition": "local" if local else "standard",
        # Identity of the database/store; travels with backups.
        "installation_id": installation(db)["id"],
    }
    if local:
        result |= {
            # Identity of this server (outside the database) and of the calling station.
            # None while the station list is unreadable: the main computer keeps working (A2).
            "server_id": (request.app.state.stations.server() or {}).get("id"),
            "network": settings.network_mode,
            "station": {"id": station["id"], "name": station["name"]} if station else None,
        }
    return result


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: DB, user: CurrentUser):
    db.execute(delete(AuthSession).where(AuthSession.token_hash == digest(request.cookies[COOKIE])))
    IdentityService(db, user).audit("logout", "users", user.id)
    response.delete_cookie(
        COOKIE,
        path="/api",
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )


@router.post("/auth/password", status_code=204, dependencies=[LoginEditionOnly])
def password(payload: schemas.PasswordChange, response: Response, db: DB, user: CurrentUser):
    IdentityService(db, user).change_password(payload.current_password, payload.new_password)
    response.delete_cookie(COOKIE, path="/api")


@router.patch("/auth/me", dependencies=[LoginEditionOnly])
def profile(payload: schemas.ProfileUpdate, db: DB, user: CurrentUser):
    service = IdentityService(db, user)
    service.audit(
        "profile.updated",
        "users",
        user.id,
        {"before": {"name": user.name}, "after": {"name": payload.name}},
    )
    user.name = payload.name
    user.updated_at = int(time.time())
    return user_view(user)


@router.get("/users", dependencies=[LoginEditionOnly, Depends(require("users.read"))])
def users(
    db: DB,
    q: str = Query("", max_length=80),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(User).where(
        User.name.contains(q, autoescape=True) | User.username.contains(q, autoescape=True)
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            user_view(u) for u in db.scalars(query.order_by(User.id).offset(offset).limit(limit))
        ],
        "total": total,
    }


@router.post("/users", status_code=201, dependencies=[LoginEditionOnly])
def create_user(
    payload: schemas.UserCreate, db: DB, actor: Annotated[User, Depends(require("users.write"))]
):
    return user_view(IdentityService(db, actor).create_user(**payload.model_dump()))


@router.patch("/users/{user_id}", dependencies=[LoginEditionOnly])
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: DB,
    actor: Annotated[User, Depends(require("users.write"))],
):
    return user_view(IdentityService(db, actor).update_user(user_id, **payload.model_dump()))


@router.post("/users/{user_id}/reset-password", status_code=204, dependencies=[LoginEditionOnly])
def reset_password(
    user_id: int,
    payload: schemas.PasswordReset,
    db: DB,
    actor: Annotated[User, Depends(require("users.write"))],
):
    service = IdentityService(db, actor)
    service.reset_password(service.get_user(user_id), payload.new_password)


def role_view(role: Role):
    return {
        "id": role.id,
        "code": role.code,
        "name": role.name,
        "permission_codes": sorted(p.code for p in role.permissions),
        "protected": role.code in {"ADMINISTRADOR", "CLIENTE"},
    }


@router.get("/roles", dependencies=[LoginEditionOnly, Depends(require("roles.read"))])
def roles(db: DB):
    return [role_view(r) for r in db.scalars(select(Role).order_by(Role.id))]


@router.get("/permissions", dependencies=[LoginEditionOnly, Depends(require("roles.read"))])
def permissions(db: DB):
    return [
        {"code": p.code, "description": p.description}
        for p in db.scalars(select(Permission).order_by(Permission.id))
    ]


@router.put("/roles/{role_id}/permissions", dependencies=[LoginEditionOnly])
def update_role(
    role_id: int,
    payload: schemas.RoleUpdate,
    db: DB,
    actor: Annotated[User, Depends(require("roles.write"))],
):
    return role_view(IdentityService(db, actor).update_role(role_id, payload.permission_codes))


@router.get("/audit-logs", dependencies=[Depends(require("audit.read"))])
def audit_logs(
    db: DB,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    station_id: str | None = Query(None, max_length=36),
):
    query = select(AuditLog)
    if station_id:
        query = query.where(AuditLog.station_id == station_id)
    return {
        "total": db.scalar(select(func.count()).select_from(query.subquery())),
        "items": [
            {
                "id": a.id,
                "occurred_at": a.occurred_at,
                "actor": a.actor_label,
                "actor_id": a.actor_id,
                "action": a.action,
                "entity": a.entity,
                "entity_id": a.entity_id,
                "changes": a.changes,
                "station_id": a.station_id,
            }
            for a in db.scalars(query.order_by(AuditLog.id.desc()).offset(offset).limit(limit))
        ],
    }
