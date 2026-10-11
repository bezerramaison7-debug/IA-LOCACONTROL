from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.service import IdentityService

PASSWORD = "Concurrency-fixture-password!"


def test_only_one_bootstrap_wins(client):
    barrier = Barrier(2)

    def bootstrap(index):
        barrier.wait()
        with Session(client.app.state.engine) as db:
            db.execute(text("BEGIN IMMEDIATE"))
            try:
                IdentityService(db, local=True).bootstrap(f"admin{index}", "Admin", PASSWORD)
                db.commit()
                return 201
            except HTTPException as error:
                db.rollback()
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(bootstrap, [1, 2]))
    assert sorted(results) == [201, 409]
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_concurrent_demotions_preserve_one_admin(client):
    with Session(client.app.state.engine) as db:
        service = IdentityService(db, local=True)
        ids = [
            service.create_user(f"admin{i}", "Admin", PASSWORD, ["ADMINISTRADOR"]).id
            for i in (1, 2)
        ]
        db.commit()
    barrier = Barrier(2)

    def demote(user_id):
        barrier.wait()
        with Session(client.app.state.engine) as db:
            db.execute(text("BEGIN IMMEDIATE"))
            try:
                IdentityService(db, local=True).update_user(
                    user_id, "Admin", False, ["ADMINISTRADOR"]
                )
                db.commit()
                return 200
            except HTTPException as error:
                db.rollback()
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(demote, ids)) == [200, 409]
    with Session(client.app.state.engine) as db:
        assert (
            db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) == 1
        )
