"""upgrade legacy administrator sessions without exposing their tokens"""

import hashlib
import string

from alembic import op
import sqlalchemy as sa


revision = "20260805_0003"
down_revision = "20260805_0002"
branch_labels = None
depends_on = None


def _column_map() -> dict[str, dict]:
    inspector = sa.inspect(op.get_bind())
    if "admin_sessions" not in inspector.get_table_names():
        raise RuntimeError("admin_sessions must exist before compatibility upgrade")
    return {
        column["name"]: column
        for column in inspector.get_columns("admin_sessions")
    }


def _valid_digest(value: object) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(character in string.hexdigits for character in text)


def upgrade() -> None:
    columns = _column_map()
    additions = (
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("created_ip", sa.String(45), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in additions:
        if column.name not in columns:
            op.add_column("admin_sessions", column)

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE admin_sessions "
            "SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP), "
            "last_used_at = COALESCE(last_used_at, created_at, CURRENT_TIMESTAMP), "
            "expires_at = COALESCE(expires_at, CURRENT_TIMESTAMP)"
        )
    )
    rows = bind.execute(
        sa.text("SELECT id, token_hash FROM admin_sessions ORDER BY id")
    ).mappings()
    seen_hashes: set[str] = set()
    for row in rows:
        current_hash = str(row["token_hash"] or "").strip().lower()
        if _valid_digest(current_hash) and current_hash not in seen_hashes:
            seen_hashes.add(current_hash)
            continue

        attempt = 0
        while True:
            replacement = hashlib.sha256(
                f"retired-admin-session:{row['id']}:{attempt}".encode("utf-8")
            ).hexdigest()
            if replacement not in seen_hashes:
                break
            attempt += 1
        seen_hashes.add(replacement)
        bind.execute(
            sa.text(
                "UPDATE admin_sessions "
                "SET token_hash = :token_hash, is_active = :is_active, "
                "revoked_at = COALESCE(revoked_at, CURRENT_TIMESTAMP) "
                "WHERE id = :id"
            ),
            {
                "token_hash": replacement,
                "is_active": False,
                "id": row["id"],
            },
        )

    unique_names = {
        constraint.get("name")
        for constraint in sa.inspect(bind).get_unique_constraints("admin_sessions")
    }
    with op.batch_alter_table("admin_sessions") as batch_op:
        batch_op.alter_column(
            "token_hash",
            existing_type=sa.String(64),
            nullable=False,
        )
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
        batch_op.alter_column(
            "last_used_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
        if "uq_admin_sessions_token_hash" not in unique_names:
            batch_op.create_unique_constraint(
                "uq_admin_sessions_token_hash",
                ["token_hash"],
            )

    index_names = {
        index.get("name")
        for index in sa.inspect(bind).get_indexes("admin_sessions")
    }
    for index_name, column_name in (
        ("ix_admin_sessions_token_hash", "token_hash"),
        ("ix_admin_sessions_expires_at", "expires_at"),
        ("ix_admin_sessions_is_active", "is_active"),
    ):
        if index_name not in index_names:
            op.create_index(index_name, "admin_sessions", [column_name])


def downgrade() -> None:
    # Administrator session history is security audit data. Preserve it.
    pass
