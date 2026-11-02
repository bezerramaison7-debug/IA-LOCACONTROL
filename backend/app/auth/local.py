"""Local edition (ADR-023): no typed credentials; operations keep their origin in the audit.

The installation id and the "operador.local" system account are created once and reused, so
existing foreign keys (created_by, actor_id...) keep pointing at a real row. The account's
password is random and never shown: nobody can sign in with it.
"""

import ipaddress
import secrets
import time
import uuid

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import Role, User
from app.auth.security import hasher
from app.contracts.models import AppSetting

INSTALLATION_KEY = "installation"
LOCAL_OPERATOR = "operador.local"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# Areas that do not exist in the local edition; their permissions are not reported to the UI.
HIDDEN_PERMISSION_GROUPS = {"users", "roles", "portal"}


def not_in_local_mode(request: Request):
    """Route guard: the feature exists only in the login-based edition."""
    if request.app.state.settings.local_mode:
        raise HTTPException(404, "Recurso indisponível na edição local.")


def installation(db: Session) -> dict:
    row = db.get(AppSetting, INSTALLATION_KEY)
    if row is None:
        row = AppSetting(
            key=INSTALLATION_KEY, value={"id": str(uuid.uuid4()), "created_at": int(time.time())}
        )
        db.add(row)
        db.flush()
    return row.value


def operator_label(db: Session) -> str:
    # Names where the action came from, never a person.
    return f"operador local · instalação {installation(db)['id'][:8]}"


def local_operator(db: Session) -> User:
    user = db.scalar(select(User).where(User.username == LOCAL_OPERATOR))
    if user is None:
        user = User(
            username=LOCAL_OPERATOR,
            name="Operador local",
            password_hash=hasher.hash(secrets.token_urlsafe(48)),
            is_active=True,
            must_change_password=False,
            roles=list(db.scalars(select(Role).where(Role.code == "ADMINISTRADOR"))),
        )
        db.add(user)
        db.flush()
    return user


def is_this_computer(request: Request) -> bool:
    """Automatic session only for a browser on this computer that addresses it as localhost.

    Loopback peer: other machines on the network never qualify (pairing is a later PR).
    Loopback Host: blocks DNS rebinding (a foreign name resolving to 127.0.0.1).
    App header: a cross-site page cannot send it without a CORS preflight, which is refused.
    """
    settings = request.app.state.settings
    try:
        peer = ipaddress.ip_address(request.client.host if request.client else "")
    except ValueError:
        return False
    origin = request.headers.get("origin")
    return (
        settings.local_mode
        and peer.is_loopback
        and request.url.hostname in LOCAL_HOSTS
        and request.headers.get("x-locacontrol-request") == "1"
        and (origin is None or origin in settings.allowed_origins)
    )
