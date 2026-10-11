import secrets
import time

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.catalog import permission_codes
from app.auth.models import AuditLog, AuthSession, LoginThrottle, Permission, Role, User
from app.auth.security import csrf_token, digest, hasher, verify_password


def user_view(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "role_codes": sorted(role.code for role in user.roles),
        "permissions": permission_codes(user),
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


class IdentityService:
    def __init__(self, db: Session, actor: User | None = None, local: bool = False):
        self.db = db
        self.actor = actor
        self.local = local

    def audit(self, action: str, entity: str, entity_id=None, changes=None):
        # Call sites supply an allowlist of non-secret fields, never request payloads.
        self.db.add(
            AuditLog(
                actor_id=self.actor.id if self.actor else None,
                actor_label=self.actor.username
                if self.actor
                else ("operador_local" if self.local else "nao_autenticado"),
                action=action,
                entity=entity,
                entity_id=str(entity_id) if entity_id is not None else None,
                changes=changes or {},
            )
        )

    def get_user(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if not user:
            raise HTTPException(404, "Usuário não encontrado.")
        return user

    def roles(self, codes: list[str]) -> list[Role]:
        roles = list(self.db.scalars(select(Role).where(Role.code.in_(set(codes)))))
        if len(roles) != len(set(codes)) or not roles:
            raise HTTPException(422, "Perfil inválido.")
        if "CLIENTE" in codes and len(set(codes)) != 1:
            raise HTTPException(422, "O perfil Cliente não pode ser combinado com perfis internos.")
        return roles

    def revoke(self, user_id: int):
        self.db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))

    def bootstrap(self, username: str, name: str, password: str) -> User:
        if self.db.scalar(select(func.count()).select_from(User)):
            raise HTTPException(
                409, "Bootstrap já realizado. Use a recuperação local se necessário."
            )
        user = self.create_user(username, name, password, ["ADMINISTRADOR"], must_change=False)
        self.audit("bootstrap.completed", "users", user.id)
        return user

    def create_user(self, username, name, password, role_codes, must_change=True) -> User:
        if self.db.scalar(select(User.id).where(User.username == username)):
            raise HTTPException(409, "Este nome de usuário já está em uso.")
        user = User(
            username=username,
            name=name,
            password_hash=hasher.hash(password),
            is_active=True,
            must_change_password=must_change,
            created_by=self.actor.id if self.actor else None,
            roles=self.roles(role_codes),
        )
        self.db.add(user)
        self.db.flush()
        self.audit(
            "user.created",
            "users",
            user.id,
            {
                "after": {
                    "username": username,
                    "name": name,
                    "role_codes": role_codes,
                    "is_active": True,
                }
            },
        )
        return user

    def update_user(self, user_id: int, name: str, is_active: bool, role_codes: list[str]):
        user = self.get_user(user_id)
        roles = self.roles(role_codes)
        was_admin = any(r.code == "ADMINISTRADOR" for r in user.roles)
        if user.is_active and was_admin and (not is_active or "ADMINISTRADOR" not in role_codes):
            admins = self.db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.is_active.is_(True), User.roles.any(Role.code == "ADMINISTRADOR"))
            )
            if admins <= 1:
                raise HTTPException(409, "É necessário manter ao menos um administrador ativo.")
        before = {
            "name": user.name,
            "is_active": user.is_active,
            "role_codes": sorted(r.code for r in user.roles),
        }
        user.name, user.is_active, user.roles = name, is_active, roles
        user.updated_at = int(time.time())
        if before["is_active"] != is_active or before["role_codes"] != sorted(set(role_codes)):
            self.revoke(user.id)
        self.audit(
            "user.updated",
            "users",
            user.id,
            {
                "before": before,
                "after": {
                    "name": name,
                    "is_active": is_active,
                    "role_codes": sorted(set(role_codes)),
                },
            },
        )
        return user

    def reset_password(self, user: User, new_password: str, action="user.password_reset"):
        user.password_hash = hasher.hash(new_password)
        user.must_change_password = True
        user.updated_at = int(time.time())
        self.revoke(user.id)
        self.db.execute(
            delete(LoginThrottle).where(LoginThrottle.key == digest("user:" + user.username))
        )
        self.audit(action, "users", user.id)

    def change_password(self, current: str, new: str):
        now = int(time.time())
        key = digest("password-change:" + str(self.actor.id))
        throttle = self.db.get(LoginThrottle, key)
        if throttle and throttle.expires_at <= now:
            self.db.delete(throttle)
            self.db.flush()
            throttle = None
        if throttle and throttle.attempts >= 5:
            raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.")
        if not verify_password(self.actor.password_hash, current):
            if throttle:
                throttle.attempts += 1
            else:
                self.db.add(LoginThrottle(key=key, attempts=1, expires_at=now + 900))
            self.audit("password.change_failed", "users", self.actor.id)
            self.db.commit()
            raise HTTPException(400, "Senha atual incorreta.")
        if current == new:
            raise HTTPException(422, "Escolha uma senha diferente da atual.")
        self.reset_password(self.actor, new, "password.changed")
        self.actor.must_change_password = False
        if throttle:
            self.db.delete(throttle)

    def login(self, username: str, password: str, ip: str, hours: int):
        now = int(time.time())
        username = username.strip().lower()
        self.db.execute(delete(LoginThrottle).where(LoginThrottle.expires_at <= now))
        self.db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
        keys = [(digest("user:" + username), 5), (digest("ip:" + ip), 30)]
        for key, limit in keys:
            throttle = self.db.get(LoginThrottle, key)
            if throttle and throttle.attempts >= limit:
                raise HTTPException(
                    429,
                    "Muitas tentativas. Aguarde 15 minutos.",
                    headers={"Retry-After": str(max(1, throttle.expires_at - now))},
                )
        user = self.db.scalar(select(User).where(User.username == username))
        valid = verify_password(user.password_hash if user else None, password)
        if not valid or not user or not user.is_active:
            for key, _limit in keys:
                throttle = self.db.get(LoginThrottle, key)
                if throttle:
                    throttle.attempts += 1
                else:
                    self.db.add(LoginThrottle(key=key, attempts=1, expires_at=now + 900))
            self.audit("login.failed", "authentication")
            self.db.commit()  # Persist throttling and failure audit even though HTTP is rejected.
            raise HTTPException(401, "Usuário ou senha inválidos.")
        if hasher.check_needs_rehash(user.password_hash):
            user.password_hash = hasher.hash(password)
        self.db.execute(delete(LoginThrottle).where(LoginThrottle.key == keys[0][0]))
        token = secrets.token_urlsafe(32)
        self.db.add(
            AuthSession(
                token_hash=digest(token),
                user_id=user.id,
                created_at=now,
                expires_at=now + hours * 3600,
            )
        )
        self.actor = user
        self.audit("login.succeeded", "users", user.id)
        return token, {"user": user_view(user), "csrf_token": csrf_token(token)}

    def update_role(self, role_id: int, codes: list[str]):
        role = self.db.get(Role, role_id)
        if not role:
            raise HTTPException(404, "Perfil não encontrado.")
        if role.code in {"ADMINISTRADOR", "CLIENTE"}:
            raise HTTPException(409, "Este perfil protegido possui permissões fixas.")
        permissions = list(
            self.db.scalars(select(Permission).where(Permission.code.in_(set(codes))))
        )
        if len(permissions) != len(set(codes)):
            raise HTTPException(422, "Permissão inválida.")
        before = sorted(p.code for p in role.permissions)
        role.permissions = permissions
        for user_id in self.db.scalars(select(User.id).where(User.roles.any(Role.id == role.id))):
            self.revoke(user_id)
        self.audit(
            "role.permissions_changed",
            "roles",
            role.id,
            {"before": before, "after": sorted(set(codes))},
        )
        return role
