"""bind computer-use jobs to the queued server template revision"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0009"
down_revision = "20260816_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "computer_use_jobs" not in set(inspector.get_table_names()):
        return
    columns = {
        column["name"]
        for column in inspector.get_columns("computer_use_jobs")
    }
    if "template_sha256" not in columns:
        op.add_column(
            "computer_use_jobs",
            sa.Column("template_sha256", sa.String(64), nullable=True),
        )


def downgrade() -> None:
    # Removing the revision binding would silently weaken queued-job integrity.
    pass
