"""Customer portal: account link, renewal requests and the portal permission."""

import sqlalchemy as sa
from alembic import op

revision = "0008_portal"
down_revision = "0007_reports"
branch_labels = None
depends_on = None

# Frozen seed: never import the evolving application catalog from a migration.
CODE = "portal.access"
DESCRIPTION = "Acessar o portal do cliente com os próprios dados"


def upgrade():
    op.create_table(
        "customer_users",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_customer_users_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_customer_users_customer_id_customers")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_customer_users_created_by_users")
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_customer_users")),
    )
    op.create_index(op.f("ix_customer_users_customer_id"), "customer_users", ["customer_id"])
    op.create_table(
        "renewal_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(12), nullable=False),
        sa.Column("period_count", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(500), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("decision_reason", sa.String(500), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDENTE','APROVADA','RECUSADA','CANCELADA')",
            name=op.f("ck_renewal_requests_status"),
        ),
        sa.CheckConstraint(
            "period IN ('DIARIA','SEMANAL','QUINZENAL','MENSAL')",
            name=op.f("ck_renewal_requests_period"),
        ),
        sa.CheckConstraint(
            "period_count > 0", name=op.f("ck_renewal_requests_positive_period_count")
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            name=op.f("fk_renewal_requests_contract_id_contracts"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_renewal_requests_customer_id_customers"),
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["users.id"], name=op.f("fk_renewal_requests_requested_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["users.id"], name=op.f("fk_renewal_requests_decided_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_renewal_requests")),
    )
    op.create_index(op.f("ix_renewal_requests_contract_id"), "renewal_requests", ["contract_id"])
    op.create_index(op.f("ix_renewal_requests_customer_id"), "renewal_requests", ["customer_id"])
    op.create_index(op.f("ix_renewal_requests_status"), "renewal_requests", ["status"])
    bind = op.get_bind()
    bind.execute(
        sa.text("INSERT INTO permissions (code, description) VALUES (:code, :description)"),
        {"code": CODE, "description": DESCRIPTION},
    )
    bind.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r, permissions p "
            "WHERE r.code = 'CLIENTE' AND p.code = :code"
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
    op.drop_index(op.f("ix_renewal_requests_status"), table_name="renewal_requests")
    op.drop_index(op.f("ix_renewal_requests_customer_id"), table_name="renewal_requests")
    op.drop_index(op.f("ix_renewal_requests_contract_id"), table_name="renewal_requests")
    op.drop_table("renewal_requests")
    op.drop_index(op.f("ix_customer_users_customer_id"), table_name="customer_users")
    op.drop_table("customer_users")
