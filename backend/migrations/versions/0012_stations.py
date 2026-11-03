"""Sessions of paired stations (network edition, ADR-025). The station list is not in the
database: it lives beside it, so a restored backup never changes pairings or revocations."""

import sqlalchemy as sa
from alembic import op

revision = "0012_stations"
down_revision = "0011_drafts"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("auth_sessions") as batch:
        batch.add_column(sa.Column("station_id", sa.String(36), nullable=True))
        batch.create_index(batch.f("ix_auth_sessions_station_id"), ["station_id"])


def downgrade():
    with op.batch_alter_table("auth_sessions") as batch:
        batch.drop_index(batch.f("ix_auth_sessions_station_id"))
        batch.drop_column("station_id")
