"""Alembic environment: load DB URL from app settings and target metadata from models."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.beijing_time_migrate import UtcEraUpgradeMarker
from app.core.config import get_settings
from app.core.database import Base, prepare_migration_engine
from app.core.migrate import compare_server_default
import app.models  # noqa: F401 — register all models on Base.metadata

config = context.config

# In-process runs (app.core.migrate) keep the app's handlers; only the CLI uses alembic.ini logging.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_url() -> str:
    return (get_settings().DATABASE_URL or "").strip()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=compare_server_default,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_url()
    if not url:
        raise RuntimeError("database is not configured")
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    prepare_migration_engine(connectable)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=compare_server_default,
            render_as_batch=connection.dialect.name == "sqlite",
            on_version_apply=UtcEraUpgradeMarker(),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
