"""Data created the way an old installation had it, before later migrations.

The current ORM maps columns added by later migrations (for instance `audit_logs.station_id`,
0013), so writing through it on an old schema fails. An old database never had rows written by
today's code: these helpers write with plain SQL on the columns that revision has.
"""

import time

from sqlalchemy import text

from app.auth.security import hasher


def legacy_account(engine, username: str, name: str, password: str, role: str = "ADMINISTRADOR"):
    """Account + role on a schema from 0002 on; returns (user_id, password_hash)."""
    hashed, now = hasher.hash(password), int(time.time())
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (username, name, password_hash, is_active, "
                "must_change_password, created_at, updated_at) "
                "VALUES (:u, :n, :h, 1, 0, :t, :t)"
            ),
            {"u": username, "n": name, "h": hashed, "t": now},
        )
        user_id = connection.execute(
            text("SELECT id FROM users WHERE username = :u"), {"u": username}
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT :id, id FROM roles WHERE code = :role"
            ),
            {"id": user_id, "role": role},
        )
    return user_id, hashed
