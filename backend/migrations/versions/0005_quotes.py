"""Quotes, items with price snapshots and status transitions."""

import sqlalchemy as sa
from alembic import op

revision = "0005_quotes"
down_revision = "0004_imports"
branch_labels = None
depends_on = None

# Frozen seed: never import the evolving application catalog from a migration.
PERMISSIONS = {
    "quotes.read": "Consultar orçamentos e baixar PDF",
    "quotes.write": "Criar, editar, enviar, cancelar e duplicar orçamentos",
    "quotes.approve": "Aprovar orçamentos",
    "quotes.negotiate": "Alterar o preço de tabela em orçamentos",
}
GRANTS = {
    "ADMINISTRADOR": list(PERMISSIONS),
    "COMERCIAL": ["quotes.read", "quotes.write", "quotes.approve"],
    "FINANCEIRO": ["quotes.read"],
}
STATUSES = "'RASCUNHO','ENVIADO','APROVADO','REJEITADO','CANCELADO','CONVERTIDO'"


def upgrade():
    op.create_table(
        "quotes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("customer_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("status_reason", sa.String(500), nullable=False),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("valid_until", sa.String(10), nullable=False),
        sa.Column("notes", sa.String(2000), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("duplicated_from_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(f"status IN ({STATUSES})", name=op.f("ck_quotes_status")),
        sa.CheckConstraint("sequence > 0", name=op.f("ck_quotes_positive_sequence")),
        sa.CheckConstraint("total_cents >= 0", name=op.f("ck_quotes_nonnegative_total")),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_quotes_customer_id_customers")
        ),
        sa.ForeignKeyConstraint(
            ["duplicated_from_id"], ["quotes.id"], name=op.f("fk_quotes_duplicated_from_id_quotes")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_quotes_created_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotes")),
        sa.UniqueConstraint("year", "sequence", name=op.f("uq_quotes_year")),
    )
    op.create_index(op.f("ix_quotes_customer_id"), "quotes", ["customer_id"])
    op.create_index(op.f("ix_quotes_status"), "quotes", ["status"])
    op.create_table(
        "quote_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(40), nullable=False),
        sa.Column("product_name", sa.String(160), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("quantity_milli", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(12), nullable=False),
        sa.Column("period_count", sa.Integer(), nullable=False),
        sa.Column("price_id", sa.Integer(), nullable=True),
        sa.Column("table_price_cents", sa.Integer(), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("end_date", sa.String(10), nullable=False),
        sa.CheckConstraint("quantity_milli > 0", name=op.f("ck_quote_items_positive_quantity")),
        sa.CheckConstraint("period_count > 0", name=op.f("ck_quote_items_positive_period_count")),
        sa.CheckConstraint(
            "period IN ('DIARIA','SEMANAL','QUINZENAL','MENSAL')",
            name=op.f("ck_quote_items_period"),
        ),
        sa.CheckConstraint(
            "table_price_cents >= 0", name=op.f("ck_quote_items_nonnegative_table_price")
        ),
        sa.CheckConstraint(
            "unit_price_cents >= 0", name=op.f("ck_quote_items_nonnegative_unit_price")
        ),
        sa.CheckConstraint("total_cents >= 0", name=op.f("ck_quote_items_nonnegative_total")),
        sa.ForeignKeyConstraint(
            ["quote_id"], ["quotes.id"], name=op.f("fk_quote_items_quote_id_quotes")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_quote_items_product_id_products")
        ),
        sa.ForeignKeyConstraint(
            ["price_id"], ["prices.id"], name=op.f("fk_quote_items_price_id_prices")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quote_items")),
    )
    op.create_index(op.f("ix_quote_items_quote_id"), "quote_items", ["quote_id"])
    op.create_index(op.f("ix_quote_items_product_id"), "quote_items", ["product_id"])
    op.create_table(
        "quote_transitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(12), nullable=True),
        sa.Column("to_status", sa.String(12), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["quote_id"], ["quotes.id"], name=op.f("fk_quote_transitions_quote_id_quotes")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_quote_transitions_created_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quote_transitions")),
    )
    op.create_index(op.f("ix_quote_transitions_quote_id"), "quote_transitions", ["quote_id"])

    bind = op.get_bind()
    for code, description in PERMISSIONS.items():
        bind.execute(
            sa.text("INSERT INTO permissions (code, description) VALUES (:code, :description)"),
            {"code": code, "description": description},
        )
    for role, codes in GRANTS.items():
        for code in codes:
            bind.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT r.id, p.id FROM roles r, permissions p "
                    "WHERE r.code = :role AND p.code = :code"
                ),
                {"role": role, "code": code},
            )


def downgrade():
    bind = op.get_bind()
    for code in PERMISSIONS:
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id IN "
                "(SELECT id FROM permissions WHERE code = :code)"
            ),
            {"code": code},
        )
        bind.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})
    op.drop_index(op.f("ix_quote_transitions_quote_id"), table_name="quote_transitions")
    op.drop_table("quote_transitions")
    op.drop_index(op.f("ix_quote_items_product_id"), table_name="quote_items")
    op.drop_index(op.f("ix_quote_items_quote_id"), table_name="quote_items")
    op.drop_table("quote_items")
    op.drop_index(op.f("ix_quotes_status"), table_name="quotes")
    op.drop_index(op.f("ix_quotes_customer_id"), table_name="quotes")
    op.drop_table("quotes")
