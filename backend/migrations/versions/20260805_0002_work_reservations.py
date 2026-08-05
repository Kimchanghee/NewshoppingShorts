"""add recoverable work reservations"""

from alembic import op
import sqlalchemy as sa

revision = "20260805_0002"
down_revision = "20260805_0001"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("work_usages")
    if "status" not in columns:
        op.add_column(
            "work_usages",
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="completed",
            ),
        )
    if "reserved_at" not in columns:
        op.add_column(
            "work_usages",
            sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "lease_expires_at" not in columns:
        op.add_column(
            "work_usages",
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        )

    inspector = sa.inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes("work_usages")}
    if "ix_work_usages_status" not in indexes:
        op.create_index("ix_work_usages_status", "work_usages", ["status"])
    if "ix_work_usages_lease_expires_at" not in indexes:
        op.create_index(
            "ix_work_usages_lease_expires_at",
            "work_usages",
            ["lease_expires_at"],
        )


def downgrade() -> None:
    # Reservation history is billing/audit data. Preserve it on rollback.
    pass
