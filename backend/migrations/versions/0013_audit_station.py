"""Station of each audited action as data, not only in the label (M4, ADR-025)."""

import sqlalchemy as sa
from alembic import op

revision = "0013_audit_station"
down_revision = "0012_stations"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(sa.Column("station_id", sa.String(36), nullable=True))
        batch.create_index(batch.f("ix_audit_logs_station_id"), ["station_id"])


def downgrade():
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_index(batch.f("ix_audit_logs_station_id"))
        batch.drop_column("station_id")
