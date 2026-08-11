"""Alembic environment using the application's validated database URL."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from app.database import Base, engine
import app.models  # noqa: F401 - register model metadata


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=engine.url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        dialect = connection.dialect.name
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        if dialect == "postgresql":
            # Supabase uses transaction pooling. Session advisory locks can be
            # returned to the pool while still held and block later deploys.
            # A transaction lock is tied to this migration transaction and is
            # released automatically on commit, rollback, or disconnect.
            with context.begin_transaction():
                connection.execute(text("SELECT pg_advisory_xact_lock(2086081106)"))
                context.run_migrations()
            return

        if dialect in {"mysql", "mariadb"}:
            value = connection.execute(
                text("SELECT GET_LOCK('ssmaker_alembic_migration', 60)")
            ).scalar()
            connection.commit()
            if value != 1:
                raise RuntimeError("Timed out waiting for the database migration lock")
            try:
                with context.begin_transaction():
                    context.run_migrations()
            finally:
                connection.execute(text("SELECT RELEASE_LOCK('ssmaker_alembic_migration')"))
                connection.commit()
            return

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
