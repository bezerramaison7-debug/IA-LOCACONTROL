"""Upload, import batches and source provenance."""

import sqlalchemy as sa
from alembic import op

revision = "0004_imports"
down_revision = "0003_masters"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "import_batches",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("imported_at", sa.Integer()),
        sa.Column("imported_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("status", sa.String(20), nullable=False),
        *[
            sa.Column(name, sa.Integer(), nullable=False)
            for name in (
                "total_rows",
                "successful_rows",
                "warning_rows",
                "failed_rows",
                "ignored_rows",
            )
        ],
        sa.Column("mapping", sa.JSON()),
        sa.Column("report", sa.JSON()),
    )
    op.create_table(
        "import_origins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_key", sa.String(64), nullable=False, unique=True),
        sa.Column("batch_id", sa.String(32), sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("sheet", sa.String(255), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("entity", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.Text(), nullable=False),
    )
    bind = op.get_bind()
    for code, description in {
        "imports.read": "Consultar importações e arquivos enviados",
        "imports.write": "Enviar Excel, validar e confirmar importações",
    }.items():
        bind.execute(
            sa.text("INSERT INTO permissions (code, description) VALUES (:code, :description)"),
            {"code": code, "description": description},
        )
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles r, permissions p "
                "WHERE r.code = 'ADMINISTRADOR' AND p.code = :code"
            ),
            {"code": code},
        )


def downgrade():
    bind = op.get_bind()
    for code in ("imports.read", "imports.write"):
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id IN "
                "(SELECT id FROM permissions WHERE code = :code)"
            ),
            {"code": code},
        )
        bind.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})
    op.drop_table("import_origins")
    op.drop_table("import_batches")
