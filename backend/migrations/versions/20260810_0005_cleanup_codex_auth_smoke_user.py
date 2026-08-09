"""remove the disposable Codex authentication smoke-test account"""

from alembic import op
import sqlalchemy as sa


revision = "20260810_0005"
down_revision = "20260808_0004"
branch_labels = None
depends_on = None


_TEST_USER_ID = 28
_TEST_USERNAME = "ui_full_1786295998_4c6d80"


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "users" not in tables:
        return

    matched_user_id = bind.execute(
        sa.text(
            "SELECT id FROM users "
            "WHERE id = :user_id AND username = :username"
        ),
        {"user_id": _TEST_USER_ID, "username": _TEST_USERNAME},
    ).scalar_one_or_none()
    if matched_user_id is None:
        return

    user_id_tables = (
        "user_logs",
        "computer_use_jobs",
        "user_settings",
        "work_usages",
        "subscription_requests",
        "sessions",
    )
    for table_name in user_id_tables:
        if table_name in tables:
            bind.execute(
                sa.text(f"DELETE FROM {table_name} WHERE user_id = :user_id"),
                {"user_id": _TEST_USER_ID},
            )

    if "login_attempts" in tables:
        bind.execute(
            sa.text("DELETE FROM login_attempts WHERE username = :username"),
            {"username": _TEST_USERNAME},
        )
    if "registration_requests" in tables:
        bind.execute(
            sa.text("DELETE FROM registration_requests WHERE username = :username"),
            {"username": _TEST_USERNAME},
        )

    bind.execute(
        sa.text("DELETE FROM users WHERE id = :user_id AND username = :username"),
        {"user_id": _TEST_USER_ID, "username": _TEST_USERNAME},
    )


def downgrade() -> None:
    # A deleted disposable account must not be recreated with its old password
    # hash or personal data during rollback.
    pass
