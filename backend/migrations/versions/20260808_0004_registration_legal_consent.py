"""record versioned terms and privacy consent for registrations"""

from alembic import op
import sqlalchemy as sa


revision = "20260808_0004"
down_revision = "20260805_0003"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        raise RuntimeError(f"{table_name} must exist before consent migration")
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("registration_requests")
    additions = (
        sa.Column("terms_accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("privacy_accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("terms_version", sa.String(32), nullable=True),
        sa.Column("privacy_version", sa.String(32), nullable=True),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("privacy_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in additions:
        if column.name not in columns:
            op.add_column("registration_requests", column)


def downgrade() -> None:
    # Consent history is legal/audit data and must not be silently discarded.
    pass
