from pathlib import Path

from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool

from app.core.config import PROJECT_ROOT


def resolve_database_url(value: str) -> URL:
    url = make_url(value)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        path = Path(url.database)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        url = url.set(database=str(path.resolve()))
    return url


def build_engine(value: str) -> Engine:
    url = resolve_database_url(value)
    options = {"pool_pre_ping": True}
    if url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False, "timeout": 5}
        if url.database in (None, "", ":memory:"):
            options["poolclass"] = StaticPool
        else:
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, **options)
    if url.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine
