from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import delete, func, select

from app.auth import schemas
from app.auth.dependencies import DB, CurrentUser, require, trusted_request
from app.auth.models import AuditLog, AuthSession, Permission, Role, User
from app.auth.security import COOKIE, csrf_token, digest
from app.auth.service import IdentityService, user_view

router = APIRouter(prefix="/api", tags=["Identidade e segurança"])


@router.post("/auth/login", dependencies=[Depends(trusted_request)])
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
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.session_hours * 3600,
        path="/api",
    )
    return result


@router.get("/auth/me")
def me(request: Request, user: CurrentUser):
    return {"user": user_view(user), "csrf_token": csrf_token(request.cookies[COOKIE])}


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


@router.post("/auth/password", status_code=204)
def password(payload: schemas.PasswordChange, response: Response, db: DB, user: CurrentUser):
    IdentityService(db, user).change_password(payload.current_password, payload.new_password)
    response.delete_cookie(COOKIE, path="/api")


@router.patch("/auth/me")
def profile(payload: schemas.ProfileUpdate, db: DB, user: CurrentUser):
    service = IdentityService(db, user)
    service.audit(
        "profile.updated",
        "users",
        user.id,
        {"before": {"name": user.name}, "after": {"name": payload.name}},
    )
    user.name = payload.name
    import time

    user.updated_at = int(time.time())
    return user_view(user)


@router.get("/users", dependencies=[Depends(require("users.read"))])
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


@router.post("/users", status_code=201)
def create_user(
    payload: schemas.UserCreate, db: DB, actor: Annotated[User, Depends(require("users.write"))]
):
    return user_view(IdentityService(db, actor).create_user(**payload.model_dump()))


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: DB,
    actor: Annotated[User, Depends(require("users.write"))],
):
    return user_view(IdentityService(db, actor).update_user(user_id, **payload.model_dump()))


@router.post("/users/{user_id}/reset-password", status_code=204)
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


@router.get("/roles", dependencies=[Depends(require("roles.read"))])
def roles(db: DB):
    return [role_view(r) for r in db.scalars(select(Role).order_by(Role.id))]


@router.get("/permissions", dependencies=[Depends(require("roles.read"))])
def permissions(db: DB):
    return [
        {"code": p.code, "description": p.description}
        for p in db.scalars(select(Permission).order_by(Permission.id))
    ]


@router.put("/roles/{role_id}/permissions")
def update_role(
    role_id: int,
    payload: schemas.RoleUpdate,
    db: DB,
    actor: Annotated[User, Depends(require("roles.write"))],
):
    return role_view(IdentityService(db, actor).update_role(role_id, payload.permission_codes))


@router.get("/audit-logs", dependencies=[Depends(require("audit.read"))])
def audit_logs(db: DB, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return {
        "total": db.scalar(select(func.count()).select_from(AuditLog)),
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
            }
            for a in db.scalars(
                select(AuditLog).order_by(AuditLog.id.desc()).offset(offset).limit(limit)
            )
        ],
    }
