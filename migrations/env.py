"""Migrations read the same validated settings as the API and worker."""

from alembic import context
from rag_core.settings import Settings
from sqlalchemy import create_engine, pool

settings = Settings()


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url.get_secret_value(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(settings.database_url.get_secret_value(), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
