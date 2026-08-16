"""scope active sessions to the program that created them"""

from alembic import op
import sqlalchemy as sa


revision = "20260816_0007"
down_revision = "20260811_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "sessions" not in set(inspector.get_table_names()):
        # Some adopted legacy databases never created session storage. The
        # application creates missing tables through its compatibility setup.
        return

    columns = {column["name"] for column in inspector.get_columns("sessions")}
    if "program_type" not in columns:
        op.add_column(
            "sessions",
            sa.Column("program_type", sa.String(20), nullable=True),
        )
        bind.execute(
            sa.text(
                "UPDATE sessions "
                "SET program_type = COALESCE(("
                "SELECT users.program_type FROM users WHERE users.id = sessions.user_id"
                "), 'ssmaker') "
                "WHERE program_type IS NULL OR program_type = ''"
            )
        )
        with op.batch_alter_table("sessions") as batch_op:
            batch_op.alter_column(
                "program_type",
                existing_type=sa.String(20),
                nullable=False,
                server_default="ssmaker",
            )

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("sessions")}
    if "ix_sessions_program_type" not in indexes:
        op.create_index(
            "ix_sessions_program_type",
            "sessions",
            ["program_type"],
            unique=False,
        )


def downgrade() -> None:
    # Session history is short-lived operational data. Keeping the column makes
    # rollback safe while older application versions simply ignore it.
    pass
