"""Automatic drafts of long forms, apart from the definitive records (ADR-024)."""

import sqlalchemy as sa
from alembic import op

revision = "0011_drafts"
down_revision = "0010_backups"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "form_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_form_drafts")),
        sa.UniqueConstraint("owner", "kind", "scope", name=op.f("uq_form_drafts_owner")),
    )
    op.create_index(op.f("ix_form_drafts_expires_at"), "form_drafts", ["expires_at"])


def downgrade():
    op.drop_index(op.f("ix_form_drafts_expires_at"), table_name="form_drafts")
    op.drop_table("form_drafts")
