"""masters

Revision ID: 0003_masters
Revises: 0002_identity
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_masters"
down_revision: str | Sequence[str] | None = "0002_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen seed: never import the evolving application catalog from a migration.
PERMISSIONS = {
    "customers.read": "Consultar clientes",
    "customers.write": "Cadastrar, editar e desativar clientes",
    "products.read": "Consultar produtos",
    "products.write": "Cadastrar, editar e desativar produtos",
    "equipment.read": "Consultar equipamentos",
    "equipment.write": "Cadastrar e editar equipamentos",
    "stock.read": "Consultar estoque e movimentos",
    "stock.write": "Movimentar estoque e situação de equipamentos",
    "prices.read": "Consultar preços e histórico",
    "prices.write": "Publicar, revisar e desativar preços",
}
GRANTS = {
    "ADMINISTRADOR": list(PERMISSIONS),
    "COMERCIAL": [
        "customers.read",
        "customers.write",
        "products.read",
        "equipment.read",
        "stock.read",
        "prices.read",
    ],
    "OPERACAO": [
        "products.read",
        "products.write",
        "equipment.read",
        "equipment.write",
        "stock.read",
        "stock.write",
    ],
    "FINANCEIRO": ["customers.read", "products.read", "prices.read", "prices.write"],
}


def upgrade() -> None:
    # Explicit schema generated from metadata, reviewed before application.
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_type", sa.String(length=2), nullable=False),
        sa.Column("legal_name", sa.String(length=160), nullable=False),
        sa.Column("trade_name", sa.String(length=160), nullable=False),
        sa.Column("document", sa.String(length=14), nullable=False),
        sa.Column("state_registration", sa.String(length=30), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("mobile", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("contact", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.CheckConstraint("person_type IN ('PF','PJ')", name=op.f("ck_customers_person_type")),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_customers_created_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
        sa.UniqueConstraint("document", name=op.f("uq_customers_document")),
    )
    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_customers_legal_name"), ["legal_name"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("individual_tracking", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_products_created_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("code", name=op.f("uq_products_code")),
    )
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_products_name"), ["name"], unique=False)

    op.create_table(
        "customer_addresses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("street", sa.String(length=200), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("postal_code", sa.String(length=8), nullable=False),
        sa.Column("label", sa.String(length=60), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_customer_addresses_customer_id_customers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_addresses")),
    )
    with op.batch_alter_table("customer_addresses", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_customer_addresses_customer_id"), ["customer_id"], unique=False
        )

    op.create_table(
        "equipment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("asset_tag", sa.String(length=80), nullable=True),
        sa.Column("serial_number", sa.String(length=100), nullable=True),
        sa.Column("brand", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('DISPONIVEL','RESERVADO','LOCADO','MANUTENCAO','INDISPONIVEL','BAIXADO')",
            name=op.f("ck_equipment_status"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_equipment_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_equipment_product_id_products")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_equipment")),
        sa.UniqueConstraint("asset_tag", name=op.f("uq_equipment_asset_tag")),
        sa.UniqueConstraint("code", name=op.f("uq_equipment_code")),
        sa.UniqueConstraint("serial_number", name=op.f("uq_equipment_serial_number")),
    )
    with op.batch_alter_table("equipment", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_equipment_product_id"), ["product_id"], unique=False)

    op.create_table(
        "prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=12), nullable=False),
        sa.Column("effective_date", sa.String(length=10), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "period IN ('DIARIA','SEMANAL','QUINZENAL','MENSAL')", name=op.f("ck_prices_period")
        ),
        sa.CheckConstraint(
            "amount_cents IS NULL OR amount_cents >= 0", name=op.f("ck_prices_nonnegative_amount")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_prices_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_prices_product_id_products")
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["prices.id"], name=op.f("fk_prices_supersedes_id_prices")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prices")),
    )
    with op.batch_alter_table("prices", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_prices_effective_date"), ["effective_date"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_prices_product_id"), ["product_id"], unique=False)

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=True),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("quantity_milli", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("request_key", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('DISPONIVEL','RESERVADO','LOCADO','MANUTENCAO','INDISPONIVEL','BAIXADO')",
            name=op.f("ck_stock_movements_from_status"),
        ),
        sa.CheckConstraint(
            "to_status IN "
            "('DISPONIVEL','RESERVADO','LOCADO','MANUTENCAO','INDISPONIVEL','BAIXADO')",
            name=op.f("ck_stock_movements_to_status"),
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status != to_status",
            name=op.f("ck_stock_movements_distinct_states"),
        ),
        sa.CheckConstraint("quantity_milli > 0", name=op.f("ck_stock_movements_positive_quantity")),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_stock_movements_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["equipment_id"],
            ["equipment.id"],
            name=op.f("fk_stock_movements_equipment_id_equipment"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_stock_movements_product_id_products")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movements")),
        sa.UniqueConstraint("request_key", name=op.f("uq_stock_movements_request_key")),
    )
    with op.batch_alter_table("stock_movements", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_stock_movements_product_id"), ["product_id"], unique=False
        )

    connection = op.get_bind()
    for code, description in PERMISSIONS.items():
        connection.execute(
            sa.text("INSERT INTO permissions (code, description) VALUES (:code, :description)"),
            {"code": code, "description": description},
        )
    for role, codes in GRANTS.items():
        for code in codes:
            connection.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT r.id, p.id FROM roles r, permissions p "
                    "WHERE r.code = :role AND p.code = :code"
                ),
                {"role": role, "code": code},
            )


def downgrade() -> None:
    connection = op.get_bind()
    for code in PERMISSIONS:
        connection.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id IN "
                "(SELECT id FROM permissions WHERE code = :code)"
            ),
            {"code": code},
        )
        connection.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})
    with op.batch_alter_table("stock_movements", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_stock_movements_product_id"))

    op.drop_table("stock_movements")
    with op.batch_alter_table("prices", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_prices_product_id"))
        batch_op.drop_index(batch_op.f("ix_prices_effective_date"))

    op.drop_table("prices")
    with op.batch_alter_table("equipment", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_equipment_product_id"))

    op.drop_table("equipment")
    with op.batch_alter_table("customer_addresses", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_customer_addresses_customer_id"))

    op.drop_table("customer_addresses")
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_products_name"))

    op.drop_table("products")
    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_customers_legal_name"))

    op.drop_table("customers")
    # ### end Alembic commands ###
