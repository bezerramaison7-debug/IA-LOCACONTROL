"""Estabelece a cadeia de migrations sem antecipar tabelas comerciais.

Revision ID: 0001_foundation
Revises: None
"""

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alembic cria e preenche alembic_version; não há schema comercial nesta etapa.
    pass


def downgrade() -> None:
    # Somente o marcador de revisão é revertido pelo próprio Alembic.
    pass
