import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)
_dummy_hash = hasher.hash(secrets.token_urlsafe(32))
COOKIE = "locacontrol_session"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(session_token: str) -> str:
    return digest("locacontrol-csrf:" + session_token)


def verify_password(stored: str | None, supplied: str) -> bool:
    try:
        valid = hasher.verify(stored or _dummy_hash, supplied)
        return bool(stored and valid)
    except (VerificationError, InvalidHashError):
        return False
