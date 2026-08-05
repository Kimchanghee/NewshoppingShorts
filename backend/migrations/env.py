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
        lock_acquired = False
        try:
            if dialect == "postgresql":
                connection.execute(text("SELECT pg_advisory_lock(2086080501)"))
                connection.commit()
                lock_acquired = True
            elif dialect in {"mysql", "mariadb"}:
                value = connection.execute(
                    text("SELECT GET_LOCK('ssmaker_alembic_migration', 60)")
                ).scalar()
                connection.commit()
                if value != 1:
                    raise RuntimeError("Timed out waiting for the database migration lock")
                lock_acquired = True

            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
        finally:
            if lock_acquired and dialect == "postgresql":
                connection.execute(text("SELECT pg_advisory_unlock(2086080501)"))
                connection.commit()
            elif lock_acquired and dialect in {"mysql", "mariadb"}:
                connection.execute(text("SELECT RELEASE_LOCK('ssmaker_alembic_migration')"))
                connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
