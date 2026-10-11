import logging
from dataclasses import dataclass
from typing import Literal

from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HealthReport:
    status: Literal["ok", "unhealthy"]
    database: Literal["ok", "unavailable"]
    schema: Literal["ok", "outdated", "unknown"]


def check_health(engine: Engine, expected_heads: set[str]) -> HealthReport:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current_heads = set(MigrationContext.configure(connection).get_current_heads())
    except SQLAlchemyError:
        logger.warning("Health check: banco indisponível.")
        return HealthReport("unhealthy", "unavailable", "unknown")

    if current_heads != expected_heads:
        return HealthReport("unhealthy", "ok", "outdated")
    return HealthReport("ok", "ok", "ok")
