"""Backup management permission. Backup settings live in app_settings."""

import sqlalchemy as sa
from alembic import op

revision = "0010_backups"
down_revision = "0009_fiscal"
branch_labels = None
depends_on = None

# Frozen seed: never import the evolving application catalog from a migration.
CODE = "backups.manage"
DESCRIPTION = "Configurar, executar, baixar e restaurar backups"


def upgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text("INSERT INTO permissions (code, description) VALUES (:code, :description)"),
        {"code": CODE, "description": DESCRIPTION},
    )
    bind.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r, permissions p "
            "WHERE r.code = 'ADMINISTRADOR' AND p.code = :code"
        ),
        {"code": CODE},
    )


def downgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code = :code)"
        ),
        {"code": CODE},
    )
    bind.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": CODE})
