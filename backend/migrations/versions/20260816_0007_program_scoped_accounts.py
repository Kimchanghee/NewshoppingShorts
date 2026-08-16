"""scope accounts, registration requests, and login attempts by program"""

from alembic import op
import sqlalchemy as sa


revision = "20260816_0007"
down_revision = "20260811_0006"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def _drop_single_username_uniqueness(table_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for index in inspector.get_indexes(table_name):
        if index.get("unique") and index.get("column_names") == ["username"]:
            op.drop_index(index["name"], table_name=table_name)

    inspector = sa.inspect(bind)
    unique_constraints = [
        constraint
        for constraint in inspector.get_unique_constraints(table_name)
        if constraint.get("column_names") == ["username"]
        and constraint.get("name")
    ]
    if unique_constraints:
        with op.batch_alter_table(table_name) as batch_op:
            for constraint in unique_constraints:
                batch_op.drop_constraint(constraint["name"], type_="unique")


def _ensure_index(
    table_name: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool,
) -> None:
    existing = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)
    }
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_present(table_name: str, index_name: str) -> None:
    existing = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)
    }
    if index_name in existing:
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    tables = _table_names()

    if "registration_requests" in tables:
        if "program_type" not in _column_names("registration_requests"):
            op.add_column(
                "registration_requests",
                sa.Column(
                    "program_type",
                    sa.String(20),
                    nullable=False,
                    server_default="ssmaker",
                ),
            )
        registration_columns = _column_names("registration_requests")
        if {"username", "program_type"} <= registration_columns:
            _drop_single_username_uniqueness("registration_requests")
            _ensure_index(
                "registration_requests",
                "ix_registration_requests_username",
                ["username"],
                unique=False,
            )
            _ensure_index(
                "registration_requests",
                "ix_registration_requests_program_type",
                ["program_type"],
                unique=False,
            )
            _ensure_index(
                "registration_requests",
                "uq_registration_requests_username_program",
                ["username", "program_type"],
                unique=True,
            )

    if "users" in tables:
        user_columns = _column_names("users")
        if {"username", "program_type"} <= user_columns:
            _drop_single_username_uniqueness("users")
            _ensure_index(
                "users", "ix_users_username", ["username"], unique=False
            )
            _ensure_index(
                "users",
                "uq_users_username_program",
                ["username", "program_type"],
                unique=True,
            )

    if "login_attempts" in tables:
        if "program_type" not in _column_names("login_attempts"):
            op.add_column(
                "login_attempts",
                sa.Column(
                    "program_type",
                    sa.String(20),
                    nullable=False,
                    server_default="ssmaker",
                ),
            )
        _ensure_index(
            "login_attempts",
            "ix_login_attempts_program_type",
            ["program_type"],
            unique=False,
        )
        _drop_index_if_present(
            "login_attempts", "ix_login_attempts_username_time"
        )
        _ensure_index(
            "login_attempts",
            "ix_login_attempts_username_program_time",
            ["username", "program_type", "attempted_at"],
            unique=False,
        )


def downgrade() -> None:
    # Accounts created with the same username in different programs cannot be
    # collapsed back into a global username namespace without deleting data.
    pass
