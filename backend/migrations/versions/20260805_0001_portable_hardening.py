"""portable security tables and legacy compatibility columns"""

import hashlib

from alembic import op
import sqlalchemy as sa

revision = "20260805_0001"
down_revision = None
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str):
    return {row["name"] for row in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column(table_name: str, column: sa.Column) -> None:
    if table_name in _tables() and column.name not in _columns(table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    tables = _tables()
    # A brand-new installation has no legacy baseline revision. Build the
    # current portable model schema first, then let Alembic stamp this revision.
    if "users" not in tables:
        from app.database import Base
        import app.models  # noqa: F401 - register every table with Base

        Base.metadata.create_all(bind=op.get_bind())
        tables = _tables()

    if "admin_sessions" not in tables:
        op.create_table(
            "admin_sessions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("created_ip", sa.String(45)),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("token_hash", name="uq_admin_sessions_token_hash"),
        )
        op.create_index("ix_admin_sessions_token_hash", "admin_sessions", ["token_hash"])
        op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])

    if "work_usages" not in tables:
        op.create_table(
            "work_usages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("idempotency_key", sa.String(36), nullable=False),
            sa.Column("success", sa.Boolean()),
            sa.Column("message", sa.String(200)),
            sa.Column("used", sa.Integer()),
            sa.Column("remaining", sa.Integer()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("user_id", "idempotency_key", name="uq_work_usage_user_key"),
        )
        op.create_index("ix_work_usages_user_id", "work_usages", ["user_id"])

    if "system_settings" not in tables:
        op.create_table(
            "system_settings",
            sa.Column("setting_key", sa.String(128), primary_key=True),
            sa.Column("setting_value", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if "user_logs" not in tables:
        op.create_table(
            "user_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("level", sa.String(20), server_default="INFO"),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("content", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_user_logs_user_id", "user_logs", ["user_id"])
        op.create_index("ix_user_logs_created_at", "user_logs", ["created_at"])

    for column in (
        sa.Column("user_type", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("program_type", sa.String(20), nullable=False, server_default="ssmaker"),
        sa.Column("current_task", sa.String(255)),
        sa.Column("is_online", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True)),
        sa.Column("app_version", sa.String(20)),
        sa.Column("trial_cycle_started_at", sa.DateTime(timezone=True)),
        sa.Column("ym_news_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("work_count", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("work_used", sa.Integer(), nullable=False, server_default="0"),
    ):
        _add_column("users", column)

    _add_column("registration_requests", sa.Column("email", sa.String(255)))
    _add_column(
        "registration_requests",
        sa.Column("ym_news_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column("billing_keys", sa.Column("enc_bill_hash", sa.String(64), nullable=True))
    if "billing_keys" in _tables():
        from app.utils.billing_crypto import decrypt_billing_key

        bind = op.get_bind()
        rows = bind.execute(
            sa.text(
                "SELECT id, enc_bill FROM billing_keys "
                "WHERE enc_bill_hash IS NULL OR enc_bill_hash = ''"
            )
        ).fetchall()
        for row in rows:
            raw_key = decrypt_billing_key(row[1])
            bind.execute(
                sa.text("UPDATE billing_keys SET enc_bill_hash = :digest WHERE id = :id"),
                {
                    "digest": hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
                    "id": row[0],
                },
            )

        unique_names = {
            constraint.get("name")
            for constraint in sa.inspect(bind).get_unique_constraints("billing_keys")
        }
        with op.batch_alter_table("billing_keys") as batch_op:
            batch_op.alter_column(
                "enc_bill_hash",
                existing_type=sa.String(64),
                nullable=False,
            )
            if "uq_user_enc_bill_hash" not in unique_names:
                batch_op.create_unique_constraint(
                    "uq_user_enc_bill_hash",
                    ["user_id", "enc_bill_hash"],
                )


def downgrade() -> None:
    # This compatibility revision may adopt pre-existing legacy tables. Their
    # ownership cannot be reconstructed safely during downgrade, so a downgrade
    # is intentionally data-preserving instead of deleting operator data.
    pass
