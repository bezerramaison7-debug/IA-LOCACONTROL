"""Reports permission. Reports only read existing tables."""

import sqlalchemy as sa
from alembic import op

revision = "0007_reports"
down_revision = "0006_contracts"
branch_labels = None
depends_on = None

# Frozen seed: never import the evolving application catalog from a migration.
CODE = "reports.read"
DESCRIPTION = "Consultar e exportar relatórios"
ROLES = ("ADMINISTRADOR", "COMERCIAL", "FINANCEIRO")


def upgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text("INSERT INTO permissions (code, description) VALUES (:code, :description)"),
        {"code": CODE, "description": DESCRIPTION},
    )
    for role in ROLES:
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles r, permissions p "
                "WHERE r.code = :role AND p.code = :code"
            ),
            {"role": role, "code": CODE},
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
