"""repair legacy system settings schema for persisted release metadata"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_0006"
down_revision = "20260810_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "system_settings" not in set(inspector.get_table_names()):
        op.create_table(
            "system_settings",
            sa.Column("setting_key", sa.String(128), primary_key=True),
            sa.Column("setting_value", sa.Text(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        return

    columns = {column["name"] for column in inspector.get_columns("system_settings")}
    if "updated_at" not in columns:
        if bind.dialect.name == "sqlite":
            # SQLite cannot ALTER ADD a column with CURRENT_TIMESTAMP as a
            # non-constant default. The portability test database only needs
            # to preserve/read legacy rows; production PostgreSQL gets the
            # strict server default below.
            op.add_column(
                "system_settings",
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            )
            bind.execute(
                sa.text(
                    "UPDATE system_settings SET updated_at = CURRENT_TIMESTAMP "
                    "WHERE updated_at IS NULL"
                )
            )
            return
        op.add_column(
            "system_settings",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )


def downgrade() -> None:
    # The repair adopts legacy operator data, so downgrade is data-preserving.
    pass
