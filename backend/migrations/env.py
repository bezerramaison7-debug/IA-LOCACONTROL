from alembic import context
from sqlalchemy import event

from app.auth import models  # noqa: F401 — register identity metadata for Alembic
from app.contracts import models as contract_models  # noqa: F401
from app.core.config import Settings
from app.drafts import models as draft_models  # noqa: F401
from app.fiscal import models as fiscal_models  # noqa: F401
from app.imports import models as import_models  # noqa: F401
from app.masters import models as master_models  # noqa: F401
from app.persistence.base import Base
from app.persistence.database import build_engine, resolve_database_url
from app.portal import models as portal_models  # noqa: F401
from app.quotes import models as quote_models  # noqa: F401

config = context.config
target_metadata = Base.metadata
# Testes usam Config.attributes sem alterar .env ou o banco de desenvolvimento.
database_url = config.attributes.get("database_url") or Settings().database_url


def run_migrations_offline():
    context.configure(
        url=resolve_database_url(database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def transactional_ddl(engine):
    """The sqlite3 driver commits DDL (ALTER, CREATE, DROP) outside any transaction, so a process
    killed in the middle of an upgrade left the schema half-migrated with the old revision and the
    next start failed ("duplicate column"). With the driver's transaction handling off and an
    explicit BEGIN, the whole upgrade is one SQLite transaction: interrupted, it rolls back
    (REL-P1E-02). SQLAlchemy recipe "Serializable isolation / Savepoints / Transactional DDL"."""

    @event.listens_for(engine, "connect")
    def driver_autocommit(dbapi_connection, _record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def explicit_begin(connection):
        connection.exec_driver_sql("BEGIN IMMEDIATE")


def run_migrations_online():
    engine = build_engine(database_url)
    if engine.dialect.name == "sqlite":
        transactional_ddl(engine)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                render_as_batch=engine.dialect.name == "sqlite",
                # One transaction for the whole upgrade (Alembic commits per migration otherwise).
                transactional_ddl=engine.dialect.name == "sqlite",
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
